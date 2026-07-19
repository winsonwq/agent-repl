import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const projectRoot = path.resolve(import.meta.dirname, "..");
const inputPath = process.argv[2] ?? path.join(projectRoot, "test-results", "workspace", "outputs", "sales_model_updated.xlsx");
const reportDir = path.join(projectRoot, "test-results", "excel-qa");
await fs.mkdir(reportDir, { recursive: true });

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const inspection = await workbook.inspect({
  kind: "table",
  range: "Sales!A1:D7",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 6,
});
await fs.writeFile(path.join(reportDir, "inspection.ndjson"), inspection.ndjson, "utf8");

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
await fs.writeFile(path.join(reportDir, "formula-errors.ndjson"), errors.ndjson, "utf8");

const preview = await workbook.render({
  sheetName: "Sales",
  range: "A1:D7",
  scale: 2,
  format: "png",
});
await fs.writeFile(
  path.join(reportDir, "sales_model_updated.png"),
  new Uint8Array(await preview.arrayBuffer()),
);

console.log(JSON.stringify({
  status: "ok",
  input: inputPath,
  inspection: path.join(reportDir, "inspection.ndjson"),
  formulaErrors: path.join(reportDir, "formula-errors.ndjson"),
  preview: path.join(reportDir, "sales_model_updated.png"),
}));
