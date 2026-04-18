const XLSX = require('xlsx');
const path = require('path');

const wb = XLSX.readFile(path.join(__dirname, 'ReferenceFile', 'World T20 Champions League 2026-2027.xlsx'));

// Groups sheet - all actual teams
const groupsData = XLSX.utils.sheet_to_json(wb.Sheets['Groups'], { header: 1, defval: '' });
const groups = {};
const headers = groupsData[0];
headers.forEach((h, col) => {
    groups[h] = [];
    for (let r = 1; r < groupsData.length; r++) {
        const val = groupsData[r][col];
        if (val && String(val).trim()) groups[h].push(String(val).trim());
    }
});
console.log('=== GROUPS ===');
Object.entries(groups).forEach(([g, teams]) => {
    console.log(`${g}: ${teams.length} teams - ${JSON.stringify(teams)}`);
});

// PT_Group_Stage - non-empty rows
const ptData = XLSX.utils.sheet_to_json(wb.Sheets['PT_Group_Stage'], { header: 1, defval: '' });
const ptRows = ptData.filter((row, i) => i > 0 && row.some(v => v !== ''));
console.log(`\n=== PT_Group_Stage (${ptRows.length} non-empty rows) ===`);
ptRows.forEach(row => console.log(JSON.stringify(row)));

// Group_Stage matches - non-empty
const matchData = XLSX.utils.sheet_to_json(wb.Sheets['Group_Stage'], { header: 1, defval: '' });
const matchRows = matchData.filter((row, i) => i > 0 && row[1] !== '');
console.log(`\n=== Group_Stage matches (${matchRows.length} total) ===`);
const completed = matchRows.filter(r => r[3] !== '' && r[3] !== undefined);
const pending = matchRows.filter(r => r[3] === '' || r[3] === undefined);
console.log(`Completed: ${completed.length}, Pending: ${pending.length}`);
completed.forEach(r => console.log(JSON.stringify(r)));
