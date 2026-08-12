import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relative) => fs.readFileSync(path.join(root, relative), 'utf8')

test('the supplied brand logo is used in the application shell', () => {
  assert.match(read('src/components/layout/Layout.tsx'), /BrandLogo/)
  assert.match(read('src/components/common/BrandLogo.tsx'), /\/qingshu-logo\.png/)
})

test('authentication pages display the same brand identity', () => {
  assert.match(read('src/pages/Login.tsx'), /BrandLogo/)
  assert.match(read('src/pages/Register.tsx'), /BrandLogo/)
})

test('the browser favicon uses the supplied brand asset', () => {
  assert.match(read('index.html'), /qingshu-logo\.png/)
})
