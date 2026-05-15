# Text-to-SQL Evaluation Strategy

1. **Execution Correctness**: Does the SQL run without errors?
2. **Result Set Match**: Does the output table match the ground truth exactly?
3. **Exact Match (EM)**: Is the generated string identical to the ground truth?
4. **Efficiency**: Does the query use correct indexes and avoid unnecessary JOINs?