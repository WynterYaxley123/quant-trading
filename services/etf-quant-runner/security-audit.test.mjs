import {test} from 'node:test';
import assert from 'node:assert/strict';
import {secretKinds} from './security-audit.mjs';

test('private key marker requires review without printing its payload',()=>{
  const sample='-----BEGIN '+'PRIVATE KEY-----';assert.ok(secretKinds(sample).includes('PRIVATE_KEY'));
});
test('empty template and synthetic references are not credential values',()=>{
  assert.deepEqual(secretKinds('API_TOKEN=\npassword=SYNTHETIC_NOT_A_REAL_PASSWORD\napi_key=process.env.API_KEY'),[]);
});
test('high-confidence non-template assignment is a candidate',()=>{
  const sample='api_key='+'FAKE'.repeat(8);assert.ok(secretKinds(sample).includes('CREDENTIAL_ASSIGNMENT'));
});
test('embedded credential URL is blocked but placeholder URL is not',()=>{
  const sample=['https','://','user',':','fake-not-real','@','host.test/path'].join('');
  assert.ok(secretKinds(sample).includes('EMBEDDED_URL_CREDENTIAL'));
  assert.deepEqual(secretKinds('https://<user>:<password>@example.invalid'),[]);
});
