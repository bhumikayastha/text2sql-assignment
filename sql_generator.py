"""
sql_generator.py  (Rule-Based, No API Key, PostgreSQL case-safe)
----------------------------------------------------------------
Uses double-quoted column names so PostgreSQL handles camelCase correctly.
"""

import re

# ── Schema ────────────────────────────────────────────────────────────────────
SCHEMA = {
    "customers":    ["customerNumber","customerName","contactLastName","contactFirstName",
                     "phone","addressLine1","city","state","postalCode","country",
                     "salesRepEmployeeNumber","creditLimit"],
    "orders":       ["orderNumber","orderDate","requiredDate","shippedDate",
                     "status","comments","customerNumber"],
    "orderdetails": ["orderNumber","productCode","quantityOrdered","priceEach","orderLineNumber"],
    "products":     ["productCode","productName","productLine","productScale",
                     "productVendor","productDescription","quantityInStock","buyPrice","MSRP"],
    "productlines": ["productLine","textDescription","htmlDescription","image"],
    "employees":    ["employeeNumber","lastName","firstName","extension",
                     "email","officeCode","reportsTo","jobTitle"],
    "offices":      ["officeCode","city","state","country","postalCode","phone","territory"],
    "payments":     ["customerNumber","checkNumber","paymentDate","amount"],
}

ALIAS = {
    "customers":"c",    "orders":"o",      "orderdetails":"od",
    "products":"p",     "productlines":"pl","employees":"e",
    "offices":"of",     "payments":"pay",
}

# ── All column names are double-quoted for PostgreSQL camelCase safety ─────────
# Format: alias."columnName"
def q(col):
    """Wrap a bare column name in double quotes."""
    return f'"{col}"'

JOIN_MAP = {
    ("orders",       "customers"):    'orders o JOIN customers c ON o."customerNumber" = c."customerNumber"',
    ("customers",    "orders"):       'customers c JOIN orders o ON c."customerNumber" = o."customerNumber"',
    ("orderdetails", "products"):     'orderdetails od JOIN products p ON od."productCode" = p."productCode"',
    ("products",     "productlines"): 'products p JOIN productlines pl ON p."productLine" = pl."productLine"',
    ("employees",    "offices"):      'employees e JOIN offices of ON e."officeCode" = of."officeCode"',
    ("customers",    "employees"):    'customers c JOIN employees e ON c."salesRepEmployeeNumber" = e."employeeNumber"',
    ("payments",     "customers"):    'payments pay JOIN customers c ON pay."customerNumber" = c."customerNumber"',
    ("orders",       "orderdetails"): 'orders o JOIN orderdetails od ON o."orderNumber" = od."orderNumber"',
    ("employees",    "employees"):    'employees e JOIN employees m ON e."reportsTo" = m."employeeNumber"',
}


# ── Detect tables ─────────────────────────────────────────────────────────────
def detect_tables(ql):
    tables = []
    if "order detail" in ql or "orderdetail" in ql:
        tables.append("orderdetails")
    if "product line description" in ql:
        if "products"     not in tables: tables.append("products")
        if "productlines" not in tables: tables.append("productlines")
    elif "product line" in ql or "productline" in ql:
        if "products" not in tables: tables.append("products")
    if "product" in ql and "products" not in tables:
        tables.append("products")
    if ("payment" in ql or "revenue" in ql) and "payments" not in tables:
        tables.append("payments")
    if "customer" in ql and "customers" not in tables:
        tables.append("customers")
    if "order" in ql and "orderdetail" not in " ".join(tables) and "orders" not in tables:
        tables.append("orders")
    if ("employee" in ql or "sales rep" in ql or "manager" in ql or "job title" in ql) \
            and "employees" not in tables:
        tables.append("employees")
    if "office" in ql and "offices" not in tables:
        tables.append("offices")

    seen, out = set(), []
    for t in tables:
        if t not in seen:
            seen.add(t); out.append(t)
    return out if out else ["customers"]


# ── Detect aggregate ──────────────────────────────────────────────────────────
def detect_agg(ql):
    if any(w in ql for w in ["how many","count","number of","total number"]): return "COUNT"
    if any(w in ql for w in ["total revenue","total payment","total stock",
                               "total quantity","sum"]):                        return "SUM"
    if any(w in ql for w in ["average","avg"]):                                return "AVG"
    if any(w in ql for w in ["max","maximum","highest"]):                      return "MAX"
    if any(w in ql for w in ["min","minimum","lowest","cheapest"]):            return "MIN"
    return ""


# ── Detect GROUP BY ───────────────────────────────────────────────────────────
def detect_group_by(ql):
    if "per country"      in ql or "by country"      in ql: return "country"
    if "per customer"     in ql or "by customer"     in ql: return '"customerNumber"'
    if "per status"       in ql or "by status"       in ql: return "status"
    if "per product line" in ql or "by product line" in ql: return '"productLine"'
    if "per office"       in ql or "by office"       in ql: return '"officeCode"'
    if "per vendor"       in ql or "by vendor"       in ql: return '"productVendor"'
    return ""


# ── Detect WHERE filter ───────────────────────────────────────────────────────
def detect_filter(ql):
    countries = [
        "usa","germany","france","uk","australia","japan","spain","italy",
        "canada","singapore","norway","denmark","finland","ireland",
        "new zealand","switzerland","netherlands","belgium","austria",
        "sweden","hong kong","philippines","russia","poland","israel"
    ]
    pattern = r"\b(?:from|in|located in|of)\s+(" + "|".join(countries) + r")\b"
    m = re.search(pattern, ql)
    if m:
        raw = m.group(1)
        fmt = " ".join(w.capitalize() for w in raw.split())
        fmt = {"Usa":"USA","Uk":"UK"}.get(fmt, fmt)
        return f"country = '{fmt}'"

    m2 = re.search(r"\b(shipped|cancelled|canceled|resolved|on hold|in process|disputed)\b", ql)
    if m2:
        return f"status = '{m2.group(1).title()}'"

    if "sales rep" in ql:
        return "\"jobTitle\" = 'Sales Rep'"

    return ""


# ── Build SELECT columns (all camelCase quoted) ───────────────────────────────
def build_columns(ql, tables, agg, group_by):
    # ── Single-value aggregates ────────────────────────────────────────────────
    if agg and not group_by and len(tables) == 1:
        t = tables[0]
        pk = {
            "customers":    '"customerNumber"',
            "products":     '"productCode"',
            "orders":       '"orderNumber"',
            "employees":    '"employeeNumber"',
            "payments":     '"checkNumber"',
            "offices":      '"officeCode"',
            "orderdetails": '"orderNumber"',
            "productlines": '"productLine"',
        }
        if agg == "COUNT":
            return f'COUNT({pk.get(t,"*")}) AS total_{t}'
        if agg == "SUM":
            if t == "payments": return 'SUM(amount) AS total_revenue'
            if t == "products": return 'SUM("quantityInStock") AS total_stock'
        if agg == "AVG":
            if "msrp" in ql:    return 'AVG("MSRP") AS avg_msrp'
            return 'AVG("buyPrice") AS avg_price'
        if agg == "MAX":
            if "payment" in ql: return 'MAX(amount) AS max_payment'
            if "msrp"    in ql: return 'MAX("MSRP") AS max_msrp'
            return 'MAX("buyPrice") AS max_price'
        if agg == "MIN":
            if "payment" in ql: return 'MIN(amount) AS min_payment'
            return 'MIN("buyPrice") AS min_price'

    # ── Grouped aggregates ────────────────────────────────────────────────────
    if agg and group_by and len(tables) == 1:
        t  = tables[0]
        pk = {
            "customers": '"customerNumber"', "orders": '"orderNumber"',
            "products":  '"productCode"',    "employees": '"employeeNumber"',
            "payments":  '"checkNumber"',
        }
        if agg == "COUNT":  return f'{group_by}, COUNT({pk.get(t,"*")}) AS total'
        if agg == "SUM":
            if t == "payments": return f'{group_by}, SUM(amount) AS total_amount'
            if t == "products": return f'{group_by}, SUM("quantityInStock") AS total_stock'
        if agg == "AVG":    return f'{group_by}, AVG("buyPrice") AS avg_buy_price'
        if agg == "MAX":
            if "msrp" in ql:    return f'{group_by}, MAX("MSRP") AS max_msrp'
            return f'{group_by}, MAX("buyPrice") AS max_buy_price'
        if agg == "MIN":    return f'{group_by}, MIN("buyPrice") AS min_buy_price'

    # ── JOIN queries ──────────────────────────────────────────────────────────
    if len(tables) >= 2:
        t1, t2 = tables[0], tables[1]
        a1, a2 = ALIAS.get(t1,"t1"), ALIAS.get(t2,"t2")
        combos = {
            ("orders",       "customers"):
                f'{a1}."orderNumber", {a1}."orderDate", {a2}."customerName"',
            ("employees",    "offices"):
                f'{a1}."firstName", {a1}."lastName", {a2}.city',
            ("payments",     "customers"):
                f'{a2}."customerName", {a1}."paymentDate", {a1}.amount',
            ("orderdetails", "products"):
                f'{a1}."orderNumber", {a2}."productName", {a1}."quantityOrdered"',
            ("products",     "productlines"):
                f'{a1}."productName", {a2}."textDescription"',
            ("customers",    "employees"):
                f'{a1}."customerName", {a2}."firstName", {a2}."lastName"',
            ("employees",    "employees"):
                'e."firstName", e."lastName", m."firstName" AS manager_first, m."lastName" AS manager_last',
        }
        if (t1, t2) in combos:
            return combos[(t1, t2)]
        return f"{a1}.*, {a2}.*"

    # ── Simple single-table selects ───────────────────────────────────────────
    t = tables[0]
    rules = [
        ("products",   r"name.*price|price.*name",      '"productName", "buyPrice"'),
        ("customers",  r"name.*cit|cit.*name",           '"customerName", city'),
        ("employees",  r"first.*last|last.*first|name",  '"firstName", "lastName"'),
        ("orders",     r"date",                          '"orderNumber", "orderDate"'),
        ("products",   r"vendor",                        'DISTINCT "productVendor"'),
        ("products",   r"code",                          '"productCode"'),
        ("offices",    r"countr",                        'DISTINCT country'),
        ("orders",     r"status",                        'DISTINCT status'),
        ("payments",   r"amount",                        '"checkNumber", amount'),
        ("employees",  r"job",                           'DISTINCT "jobTitle"'),
        ("customers",  r"phone",                         '"customerName", phone'),
        ("products",   r"msrp",                          '"productName", "MSRP"'),
        ("orders",     r"number",                        '"orderNumber"'),
    ]
    for tbl, pat, cols in rules:
        if t == tbl and re.search(pat, ql):
            return cols
    return "*"


# ── Assemble final SQL ────────────────────────────────────────────────────────
def build_sql(tables, columns, where, group_by):
    if len(tables) == 1:
        t = tables[0]
        from_clause = f"{t} {ALIAS.get(t, t)}"

    elif len(tables) == 2:
        t1, t2 = tables[0], tables[1]
        if t1 == "employees" and t2 == "employees":
            from_clause = 'employees e JOIN employees m ON e."reportsTo" = m."employeeNumber"'
        elif (t1, t2) in JOIN_MAP:
            from_clause = JOIN_MAP[(t1, t2)]
        elif (t2, t1) in JOIN_MAP:
            from_clause = JOIN_MAP[(t2, t1)]
        else:
            a1, a2 = ALIAS.get(t1,t1), ALIAS.get(t2,t2)
            from_clause = f"{t1} {a1}, {t2} {a2}"
    else:
        t1, t2 = tables[0], tables[1]
        key = (t1,t2) if (t1,t2) in JOIN_MAP else (t2,t1)
        from_clause = JOIN_MAP.get(key, f"{t1} {ALIAS.get(t1,t1)}, {t2} {ALIAS.get(t2,t2)}")
        for t in tables[2:]:
            from_clause += f" JOIN {t} {ALIAS.get(t,t)}"

    sql = f"SELECT {columns}\nFROM {from_clause}"
    if where:
        sql += f"\nWHERE {where}"
    if group_by:
        sql += f"\nGROUP BY {group_by}"
    sql += ";"
    return sql


# ── Public API ────────────────────────────────────────────────────────────────
def decompose_question(question):
    ql = question.strip().lower()
    tables   = detect_tables(ql)
    agg      = detect_agg(ql)
    group_by = detect_group_by(ql)
    where    = detect_filter(ql)
    columns  = build_columns(ql, tables, agg, group_by)

    joins = []
    if len(tables) == 2:
        key = (tables[0], tables[1])
        if key in JOIN_MAP:
            joins = [JOIN_MAP[key]]
        elif tables[0] == "employees" and tables[1] == "employees":
            joins = [JOIN_MAP[("employees","employees")]]

    if agg and group_by:
        intent = f"{agg} grouped by {group_by} from {', '.join(tables)}"
    elif agg:
        intent = f"Get single {agg} value from {', '.join(tables)}"
    elif len(tables) > 1:
        intent = f"Retrieve joined data from {' + '.join(tables)}"
    else:
        intent = f"Retrieve records from {tables[0]}"

    return {
        "intent":   intent,
        "tables":   tables,
        "columns":  [columns],
        "filters":  [where] if where else [],
        "joins":    joins,
        "group_by": group_by,
        "_agg":     agg,
        "_where":   where,
    }


def generate_sql(question):
    """Main entry: question -> (sql, decomposition)"""
    print(f"[SQL_GENERATOR] Processing: '{question}'")
    decomp   = decompose_question(question)
    tables   = decomp["tables"]
    columns  = decomp["columns"][0]
    where    = decomp["_where"]
    group_by = decomp["group_by"]
    sql      = build_sql(tables, columns, where, group_by)

    print(f"[SQL_GENERATOR] Intent:   {decomp['intent']}")
    print(f"[SQL_GENERATOR] Tables:   {tables}")
    print(f"[SQL_GENERATOR] Columns:  {columns}")
    print(f"[SQL_GENERATOR] Filter:   {where or 'None'}")
    print(f"[SQL_GENERATOR] Group by: {group_by or 'None'}")
    print(f"[SQL_GENERATOR] SQL:      {sql}")
    return sql, decomp


def fix_sql(question, broken_sql, error_message):
    """Auto-fix broken SQL using the PostgreSQL error message."""
    print(f"[SQL_GENERATOR] Fixing SQL. Error: {error_message[:100]}")
    fixed = broken_sql

    # Wrong table name
    m = re.search(r'relation "(\w+)" does not exist', error_message)
    if m:
        bad = m.group(1)
        for correct in SCHEMA:
            if correct.startswith(bad[:4]) or bad in correct:
                fixed = fixed.replace(bad, correct)
                print(f"[SQL_GENERATOR] Fixed table: {bad} -> {correct}")
                break

    # Column does not exist → add double quotes
    m2 = re.search(r'column "([^"]+)" does not exist', error_message)
    if m2:
        bad_col = m2.group(1)
        # Try adding double quotes around just the column part
        fixed = fixed.replace(f"({bad_col})", f'("{bad_col}")')
        fixed = fixed.replace(f" {bad_col} ", f' "{bad_col}" ')
        print(f"[SQL_GENERATOR] Quoted column: {bad_col}")

    # Syntax error → regenerate completely
    if "syntax error" in error_message.lower():
        print(f"[SQL_GENERATOR] Syntax error - regenerating from scratch")
        new_sql, _ = generate_sql(question)
        return new_sql

    # Ambiguous column → qualify with alias
    m3 = re.search(r'column reference "(\w+)" is ambiguous', error_message)
    if m3:
        col = m3.group(1)
        for tbl, cols in SCHEMA.items():
            if col in cols:
                a = ALIAS.get(tbl, tbl)
                fixed = re.sub(r'\b' + col + r'\b', f'{a}."{col}"', fixed)
                print(f"[SQL_GENERATOR] Fixed ambiguous: {col} -> {a}.\"{col}\"")
                break

    if not fixed.endswith(";"):
        fixed += ";"
    return fixed


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "What is the number of customers",
        "How many customers are from Germany",
        "List all products",
        "Get orders with customer names",
        "Count customers per country",
        "Total revenue from payments",
        "Average buy price per product line",
        "Get employees and their manager",
        "Total number of customers",
        "Max payment amount",
        "Get payments with customer names",
        "Show all order statuses",
    ]
    print("=" * 65)
    print("SQL GENERATOR SELF-TEST")
    print("=" * 65)
    for t in tests:
        sql, _ = generate_sql(t)
        print(f"  => {sql}\n")
