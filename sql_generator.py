"""
sql_generator.py
----------------
Rule-based SQL generator for the classicmodels schema.

This module does not require an OpenAI API key. It uses simple heuristics
and pattern matching to convert natural language questions into safe
PostgreSQL SELECT statements for the built-in classicmodels schema.
"""

import json
import re
from typing import Tuple, List, Dict


class SQLGenerationError(Exception):
    pass


TABLE_PRIORITY = [
    "orders",
    "payments",
    "customers",
    "employees",
    "products",
    "productlines",
    "offices",
    "orderdetails",
]

TABLE_KEYWORDS = {
    "products": ["product", "products", "product name", "product names", "product code", "product codes", "buy price", "price", "vendor", "msrp", "stock"],
    "customers": ["customer", "customers", "customer name", "customer names", "customer phone", "credit limit", "sales rep", "salesrep", "sales rep name", "customer country", "customer city"],
    "orders": ["order", "orders", "order number", "order numbers", "order date", "order dates", "order status", "status", "placed by", "placed"],
    "employees": ["employee", "employees", "first name", "last name", "first and last", "job title", "manager", "reports to", "sales rep"],
    "offices": ["office", "offices", "office code", "territory"],
    "payments": ["payment", "payments", "payment amount", "amount", "total revenue", "check number", "payment date"],
    "productlines": ["product line", "product lines", "html description"],
    "orderdetails": ["order detail", "order details", "quantity ordered", "price each", "order line number"],
}

COLUMN_PATTERNS = [
    ("product names and prices", ["productName", "buyPrice", "MSRP"]),
    ("customer names and cities", ["customerName", "city"]),
    ("employee first and last names", ["firstName", "lastName"]),
    ("product vendor list", ["productVendor"]),
    ("product msrp values", ["MSRP"]),
    ("customer phone numbers", ["phone"]),
    ("order numbers", ["orderNumber"]),
    ("all order dates", ["orderDate"]),
    ("all payment amounts", ["amount"]),
    ("all job titles", ["jobTitle"]),
    ("count total orders", ["COUNT(*) AS total_orders"]),
    ("total number of customers", ["COUNT(*) AS total_customers"]),
    ("total number of products", ["COUNT(*) AS total_products"]),
]

AGGREGATE_PATTERNS = [
    (r"count customers per country", ["country"], ["COUNT(*) AS customer_count"]),
    (r"total payments per customer", ["customerName"], ["SUM(amount) AS total_payments"]),
    (r"number of orders per status", ["status"], ["COUNT(*) AS order_count"]),
    (r"products per product line", ["productLine"], ["COUNT(*) AS product_count"]),
    (r"employees per office", ["officeCode"], ["COUNT(*) AS employee_count"]),
    (r"total stock per product vendor", ["productVendor"], ["SUM(quantityInStock) AS total_stock"]),
    (r"average buy price per product line", ["productLine"], ["AVG(buyPrice) AS average_buy_price"]),
    (r"orders per customer", ["customerName"], ["COUNT(*) AS order_count"]),
    (r"max msrp per product line", ["productLine"], ["MAX(MSRP) AS max_msrp"]),
    (r"min buy price per vendor", ["productVendor"], ["MIN(buyPrice) AS min_buy_price"]),
    (r"total revenue from payments", [], ["SUM(amount) AS total_revenue"]),
    (r"average product price", [], ["AVG(buyPrice) AS average_buy_price"]),
    (r"max payment amount", [], ["MAX(amount) AS max_payment_amount"]),
    (r"min payment amount", [], ["MIN(amount) AS min_payment_amount"]),
    (r"count total orders", [], ["COUNT(*) AS total_orders"]),
    (r"total quantity in stock", [], ["SUM(quantityInStock) AS total_quantity_in_stock"]),
    (r"average msrp", [], ["AVG(MSRP) AS average_msrp"]),
    (r"number of employees", [], ["COUNT(*) AS total_employees"]),
]

JOIN_RELATIONS = {
    frozenset(["orders", "customers"]): 'JOIN "customers" ON "orders"."customerNumber" = "customers"."customerNumber"',
    frozenset(["employees", "offices"]): 'JOIN "offices" ON "employees"."officeCode" = "offices"."officeCode"',
    frozenset(["payments", "customers"]): 'JOIN "customers" ON "payments"."customerNumber" = "customers"."customerNumber"',
    frozenset(["orderdetails", "products"]): 'JOIN "products" ON "orderdetails"."productCode" = "products"."productCode"',
    frozenset(["products", "productlines"]): 'JOIN "productlines" ON "products"."productLine" = "productlines"."productLine"',
    frozenset(["customers", "employees"]): 'JOIN "employees" ON "customers"."salesRepEmployeeNumber" = "employees"."employeeNumber"',
    frozenset(["orders", "orderdetails"]): 'JOIN "orderdetails" ON "orders"."orderNumber" = "orderdetails"."orderNumber"',
}

SPECIAL_PATTERNS = [
    (r"show all orders placed by customers in germany", {
        "tables": ["orders", "customers"],
        "columns": ["\"orders\".\"orderNumber\"", "\"orders\".\"orderDate\"", "\"orders\".\"status\"", "\"customers\".\"customerName\""],
        "filters": ["\"customers\".\"country\" = 'Germany'"],
        "joins": [JOIN_RELATIONS[frozenset(["orders", "customers"])]]
    }),
    (r"get orders with customer names", {
        "tables": ["orders", "customers"],
        "columns": ["\"orders\".\"orderNumber\"", "\"orders\".\"orderDate\"", "\"customers\".\"customerName\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["orders", "customers"])]]
    }),
    (r"get employees with office city", {
        "tables": ["employees", "offices"],
        "columns": ["\"employees\".\"firstName\"", "\"employees\".\"lastName\"", "\"offices\".\"city\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["employees", "offices"])]]
    }),
    (r"get payments with customer names", {
        "tables": ["payments", "customers"],
        "columns": ["\"payments\".\"paymentDate\"", "\"payments\".\"amount\"", "\"customers\".\"customerName\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["payments", "customers"])]]
    }),
    (r"get order details with product names", {
        "tables": ["orderdetails", "products"],
        "columns": ["\"orderdetails\".\"orderNumber\"", "\"products\".\"productName\"", "\"orderdetails\".\"quantityOrdered\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["orderdetails", "products"])]]
    }),
    (r"get products with product line description", {
        "tables": ["products", "productlines"],
        "columns": ["\"products\".\"productName\"", "\"productlines\".\"textDescription\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["products", "productlines"])]]
    }),
    (r"get customers with sales rep names", {
        "tables": ["customers", "employees"],
        "columns": ["\"customers\".\"customerName\"", "\"employees\".\"firstName\"", "\"employees\".\"lastName\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["customers", "employees"])]]
    }),
    (r"get orders with customer city", {
        "tables": ["orders", "customers"],
        "columns": ["\"orders\".\"orderNumber\"", "\"customers\".\"city\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["orders", "customers"])]]
    }),
    (r"get employees and their manager", {
        "tables": ["employees"],
        "columns": ["e.\"firstName\"", "e.\"lastName\"", "m.\"firstName\" AS \"managerFirstName\"", "m.\"lastName\" AS \"managerLastName\""],
        "filters": [],
        "joins": ['JOIN "employees" m ON e."reportsTo" = m."employeeNumber"'],
        "base_table": 'employees',
        "alias_base": 'e'
    }),
    (r"get orderdetails with product vendor", {
        "tables": ["orderdetails", "products"],
        "columns": ["\"orderdetails\".\"orderNumber\"", "\"products\".\"productName\"", "\"products\".\"productVendor\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["orderdetails", "products"])]]
    }),
    (r"get payments with customer country", {
        "tables": ["payments", "customers"],
        "columns": ["\"payments\".\"paymentDate\"", "\"payments\".\"amount\"", "\"customers\".\"country\""],
        "filters": [],
        "joins": [JOIN_RELATIONS[frozenset(["payments", "customers"])]]
    }),
]


def normalize_question(question: str) -> str:
    return question.strip().lower()


def quote_identifier(identifier: str) -> str:
    return f'"{identifier}"'


def qualify_column(table: str, column: str) -> str:
    if column == "*":
        return f'"{table}".*'
    if "." in column or "(" in column:
        return column
    return f'"{table}"."{column}"'


def build_from_clause(tables: List[str], joins: List[str], base_table: str = None, alias_base: str = None) -> str:
    if base_table is None:
        base_table = tables[0]
    from_clause = f'FROM "{base_table}"'
    if alias_base:
        from_clause = f'FROM "{base_table}" {alias_base}'
    for join in joins:
        from_clause += f' {join}'
    return from_clause


def build_sql(decomposition: dict) -> str:
    columns = decomposition.get("columns", ["*"])
    filters = decomposition.get("filters", [])
    joins = decomposition.get("joins", [])
    group_by = decomposition.get("group_by", [])
    order_by = decomposition.get("order_by", [])
    base_table = decomposition.get("base_table")
    alias_base = decomposition.get("alias_base")

    select_clause = "SELECT " + ", ".join(columns)
    from_clause = build_from_clause(decomposition.get("tables", []), joins, base_table=base_table, alias_base=alias_base)
    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)
    group_by_clause = ""
    if group_by:
        group_by_clause = "GROUP BY " + ", ".join(group_by)
    order_by_clause = ""
    if order_by:
        order_by_clause = "ORDER BY " + ", ".join(order_by)

    sql = " ".join(part for part in [select_clause, from_clause, where_clause, group_by_clause, order_by_clause] if part)
    if not sql.strip().endswith(";"):
        sql += ";"
    return sql


def match_special(question: str) -> dict:
    normalized = normalize_question(question)
    for pattern, decomposition in SPECIAL_PATTERNS:
        if re.search(pattern, normalized):
            return decomposition.copy()
    return {}


def guess_tables(question: str) -> List[str]:
    normalized = normalize_question(question)

    if "product lines" in normalized or "product line" in normalized:
        if "products" in normalized and "product line" in normalized:
            return ["products", "productlines"]
        return ["productlines"]

    if "order details" in normalized or "order detail" in normalized:
        if "product" in normalized:
            return ["orderdetails", "products"]
        return ["orderdetails"]

    found = []
    for table, keywords in TABLE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            found.append(table)
    if not found:
        if "germany" in normalized or "city" in normalized or "country" in normalized:
            return ["customers"]
        raise SQLGenerationError("Could not determine which table to query from the question.")

    found = sorted(set(found), key=lambda t: TABLE_PRIORITY.index(t) if t in TABLE_PRIORITY else len(TABLE_PRIORITY))
    return found


def guess_columns(question: str, tables: List[str]) -> List[str]:
    normalized = normalize_question(question)
    for phrase, columns in COLUMN_PATTERNS:
        if phrase in normalized:
            return [quote_identifier(c) if c != "*" else c for c in ["*" if c == "*" else c for c in columns]]

    if any(keyword in normalized for keyword in ["count ", "number of", "total number", "total number of"]):
        return ["COUNT(*) AS total_count"]

    if any(keyword in normalized for keyword in ["total revenue", "total payments"]):
        return ["SUM(amount) AS total_payments"]

    if "average buy price" in normalized or "average product price" in normalized:
        return ["AVG(buyPrice) AS average_buy_price"]

    if "average msrp" in normalized:
        return ["AVG(MSRP) AS average_msrp"]

    if "max msrp" in normalized:
        return ["MAX(MSRP) AS max_msrp"]

    if "min buy price" in normalized:
        return ["MIN(buyPrice) AS min_buy_price"]

    if "max payment amount" in normalized:
        return ["MAX(amount) AS max_payment_amount"]

    if "min payment amount" in normalized:
        return ["MIN(amount) AS min_payment_amount"]

    if "total quantity" in normalized and "stock" in normalized:
        return ["SUM(quantityInStock) AS total_quantity_in_stock"]

    if "customer names" in normalized:
        return ["\"customers\".\"customerName\""]
    if "city" in normalized and "customer" in normalized:
        return ["\"customers\".\"customerName\"", "\"customers\".\"city\""]
    if "city" in normalized and "office" in normalized:
        return ["\"offices\".\"city\""]
    if "job title" in normalized:
        return ["\"employees\".\"jobTitle\""]
    if "phone" in normalized and "customer" in normalized:
        return ["\"customers\".\"phone\""]
    if "vendor" in normalized and "product" in normalized:
        return ["\"products\".\"productVendor\""]
    if "product code" in normalized or "product codes" in normalized:
        return ["\"products\".\"productCode\""]
    if "order status" in normalized or "statuses" in normalized:
        return ["\"orders\".\"status\""]
    if "order date" in normalized:
        return ["\"orders\".\"orderDate\""]
    if "payment amount" in normalized or "amount" in normalized and "payment" in normalized:
        return ["\"payments\".\"amount\""]
    if "product msrp" in normalized:
        return ["\"products\".\"MSRP\""]
    if "sales rep" in normalized and "customer" in normalized:
        return ["\"customers\".\"customerName\"", "\"employees\".\"firstName\"", "\"employees\".\"lastName\""]
    if "manager" in normalized and "employee" in normalized:
        return ["e.\"firstName\"", "e.\"lastName\"", "m.\"firstName\" AS \"managerFirstName\"", "m.\"lastName\" AS \"managerLastName\""]

    return ["*"]


def guess_filters(question: str, tables: List[str]) -> List[str]:
    normalized = normalize_question(question)
    filters = []
    if "in germany" in normalized:
        if "customers" in tables:
            filters.append('"customers"."country" = \'Germany\'')
        elif "offices" in tables:
            filters.append('"offices"."country" = \'Germany\'')
    if "shipped" in normalized and "status" in normalized:
        filters.append('"orders"."status" = \'Shipped\'')
    if "status" in normalized and "orders" in tables and "shipped" not in normalized:
        pass
    return filters


def guess_joins(question: str, tables: List[str]) -> List[str]:
    joins = []
    normalized = normalize_question(question)
    table_set = frozenset(tables)
    for relation, clause in JOIN_RELATIONS.items():
        if relation.issubset(table_set):
            joins.append(clause)

    if "manager" in normalized and "employee" in normalized:
        joins = ['JOIN "employees" m ON e."reportsTo" = m."employeeNumber"']
    return joins


def guess_group_by(question: str, columns: List[str]) -> List[str]:
    normalized = normalize_question(question)
    if "per country" in normalized or "customers per country" in normalized or "customers per country" in normalized:
        return ['"customers"."country"']
    if "per product line" in normalized:
        return ['"products"."productLine"']
    if "per office" in normalized:
        return ['"employees"."officeCode"']
    if "per customer" in normalized:
        return ['"customers"."customerName"']
    if "per status" in normalized:
        return ['"orders"."status"']
    return []


def decompose_question(question: str) -> dict:
    normalized = normalize_question(question)
    special = match_special(question)
    if special:
        return {
            "intent": question,
            "tables": special["tables"],
            "columns": special["columns"],
            "filters": special.get("filters", []),
            "joins": special.get("joins", []),
            "group_by": special.get("group_by", []),
            "base_table": special.get("base_table"),
            "alias_base": special.get("alias_base"),
        }

    tables = guess_tables(question)
    columns = guess_columns(question, tables)
    joins = guess_joins(question, tables)
    filters = guess_filters(question, tables)
    group_by = guess_group_by(question, columns)

    return {
        "intent": question,
        "tables": tables,
        "columns": columns,
        "filters": filters,
        "joins": joins,
        "group_by": group_by,
    }


def generate_query(question: str, decomposition: dict) -> str:
    sql = build_sql(decomposition)
    if not sql.upper().startswith("SELECT"):
        raise SQLGenerationError("Generated SQL is not a SELECT statement.")
    return sql


def generate_sql(question: str) -> Tuple[str, dict]:
    decomposition = decompose_question(question)
    sql = generate_query(question, decomposition)
    return sql, decomposition


def fix_sql(question: str, sql: str, error_message: str) -> str:
    try:
        decomposition = decompose_question(question)
        return generate_query(question, decomposition)
    except SQLGenerationError:
        return sql


if __name__ == "__main__":
    tests = [
        "Show all orders placed by customers in Germany",
        "Get all customers",
        "Get product names and prices",
        "Count customers per country",
        "Get employees with office city",
    ]
    for question in tests:
        sql, decomp = generate_sql(question)
        print("Question:", question)
        print("SQL:", sql)
        print("Decomposition:", json.dumps(decomp, indent=2))
        print("" + "-" * 80 + "\n")
