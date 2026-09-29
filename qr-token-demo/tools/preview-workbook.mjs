import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const file = process.argv[2];
const output = process.argv[3] || 'tools/previews';
await fs.mkdir(output, {recursive:true});
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
console.log((await workbook.inspect({kind:'sheet', include:'id,name'})).ndjson);
const ranges=['A1:F18','A1:H19','A1:I13','A1:G24','A1:H34','A1:G9','A1:G16','A1:F16','A1:G11','A1:H18'];
for (let i=0;i<workbook.worksheets.items.length;i++) {
  const sheet = workbook.worksheets.items[i];
  const blob = await workbook.render({sheetName:sheet.name,range:ranges[i],scale:1,format:'png'});
  await fs.writeFile(path.join(output, `${i+1}.png`),new Uint8Array(await blob.arrayBuffer()));
}
