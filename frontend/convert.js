const fs = require('fs');
try {
  const content = fs.readFileSync('ts_errors.txt', 'utf16le');
  fs.writeFileSync('ts_errors_utf8.txt', content, 'utf8');
  console.log('Done');
} catch(e) {
  fs.writeFileSync('ts_errors_utf8.txt', e.toString(), 'utf8');
}
