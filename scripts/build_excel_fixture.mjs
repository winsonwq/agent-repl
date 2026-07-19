import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = path.resolve(import.meta.dirname, "..");
const outputDir = path.join(projectRoot, "tests", "fixtures");
await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("Sales");
sheet.showGridLines = false;
sheet.freezePanes.freezeRows(3);

sheet.getRange("A1:D1").merge();
sheet.getRange("A1").values = [["Monthly Sales Model"]];
sheet.getRange("A1:D1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  rowHeight: 28,
};

sheet.getRange("A3:D7").values = [
  ["Month", "Revenue", "Cost", "Profit"],
  ["Jan", 1000, 650, null],
  ["Feb", 1200, 700, null],
  ["Mar", 1300, 780, null],
  ["Total", null, null, null],
];
sheet.getRange("D4").formulas = [["=B4-C4"]];
sheet.getRange("D4:D6").fillDown();
sheet.getRange("B7").formulas = [["=SUM(B4:B6)"]];
sheet.getRange("C7").formulas = [["=SUM(C4:C6)"]];
sheet.getRange("D7").formulas = [["=SUM(D4:D6)"]];

sheet.getRange("A3:D3").format = {
  fill: "#D9EAF7",
  font: { bold: true, color: "#17365D" },
  borders: { preset: "outside", style: "thin", color: "#7F8C8D" },
};
sheet.getRange("A7:D7").format = {
  fill: "#E2F0D9",
  font: { bold: true, color: "#375623" },
  borders: { preset: "doubleBottom", style: "thin", color: "#548235" },
};
sheet.getRange("B4:D7").format.numberFormat = '"$"#,##0';
sheet.getRange("A3:D7").format.borders = {
  insideHorizontal: { style: "thin", color: "#D9E2F3" },
};
sheet.getRange("A1:D7").format.autofitColumns();
sheet.getRange("A:A").format.columnWidth = 14;
sheet.getRange("B:D").format.columnWidth = 16;

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(outputDir, "sales_model.xlsx"));

const preview = await workbook.render({
  sheetName: "Sales",
  range: "A1:D7",
  scale: 2,
  format: "png",
});
await fs.writeFile(
  path.join(outputDir, "sales_model.png"),
  new Uint8Array(await preview.arrayBuffer()),
);

const check = await workbook.inspect({
  kind: "table",
  range: "Sales!A1:D7",
  include: "values,formulas",
  tableMaxRows: 10,
  tableMaxCols: 6,
});
console.log(check.ndjson);
