// Regenerates adminbilling_golden.json from the AdminBilling board. Input: the board page saved as page_admin_billing_raw.html
// (decode the "Admin: billing and rent" page from HH Stay and Rent Screens.html). Run: node generate_golden.js
// The output file name here is adminbilling_golden_raw.json: copy its cases into adminbilling_golden.json.
const fs = require('fs');
const html = fs.readFileSync('page_admin_billing_raw.html', 'utf8');
const start = html.indexOf('class Component extends DCLogic');
const end = html.indexOf('</script>', start);
const src = html.slice(start, end);
class DCLogic { constructor(props) { this.props = props; } setState(s) { this.state = Object.assign({}, this.state, s); } }
const Component = new Function('DCLogic', src + '\nreturn Component;')(DCLogic);
const out = [];
const joinsLabel = ['18 Sep 2026', '31 Jan 2027', '1 Sep 2026', '5 Sep 2026'];
function grab(state) {
  const c = new Component({});
  c.state = Object.assign({}, c.state, state);
  const v = c.renderVals();
  return { rows: v.rows, summary: v.summary };
}
for (let j = 0; j < 4; j++) {
  const r = grab({ mode: 'ANN', join: j });
  out.push({ mode: 'ANNIVERSARY', day: null, policy: null, join: joinsLabel[j], rows: r.rows, summary: r.summary });
  for (const day of [1, 5, 10, 15, 'LAST']) {
    for (const policy of ['PRORATE', 'FULL']) {
      const r2 = grab({ mode: 'FIX', day, policy, join: j });
      out.push({ mode: 'FIXED_DAY', day: day === 'LAST' ? 'LAST_DAY' : day, policy: policy === 'FULL' ? 'FULL_MONTH' : 'PRORATE', join: joinsLabel[j], rows: r2.rows, summary: r2.summary });
    }
  }
}
fs.writeFileSync('adminbilling_golden_raw.json', JSON.stringify(out, null, 1), 'utf8');
console.log('cases', out.length);
console.log(JSON.stringify(out.find(o => o.mode === 'FIXED_DAY' && o.day === 1 && o.policy === 'PRORATE' && o.join === '18 Sep 2026'), null, 1));
