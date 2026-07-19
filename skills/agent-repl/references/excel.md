# Excel workflow

Import and open the workbook explicitly:

```python
from agent_repl_excel import excel
wb = excel.open("relative/path.xlsx")
```

The Runtime creates a working copy. Inspect sheets and relevant ranges before changing them. Apply targeted values, formulas, and formatting without rebuilding unrelated content.

When formulas change, recalculate, run `wb.scan_formula_errors()`, and check cached values when correctness depends on calculation results. Publish the verified workbook with `wb.save_output(...)` under `outputs/`.
