import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'))

function numeric(version) {
  return version.split('.').slice(0, 3).map((part) => Number.parseInt(part, 10))
}

function atLeast(actual, minimum) {
  const left = numeric(actual)
  const right = numeric(minimum)
  return left.some((part, index) => part > right[index] && left.slice(0, index).every((v, i) => v === right[i]))
    || left.every((part, index) => part === right[index])
}

test('react-router stays outside the audited vulnerable range', () => {
  const resolved = lock.packages['node_modules/react-router-dom']?.version
  assert.ok(resolved, 'react-router-dom must remain locked')
  assert.equal(atLeast(resolved, '7.18.2'), true, `resolved ${resolved} is below 7.18.2`)
})

test('CAPTCHA providers remain intentionally out of this release package', () => {
  const names = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies }).join(' ').toLowerCase()
  assert.doesNotMatch(names, /captcha|recaptcha|hcaptcha|turnstile/)
})
