// @mathieuc/tradingview 래퍼
//
// 트레이딩뷰가 전략 리포트(dataCompressed)를 zip 이 아닌 zlib(deflate) 으로 보내게 바뀌어
// 라이브러리 내장 parseCompressed 가 "Can't find end of central directory" 로 실패한다.
// 라이브러리가 로드되기 전에 parseCompressed 를 교체해 zlib / gzip / zip 을 모두 처리한다.
// (study.js 가 require 시점에 구조분해로 가져가므로 반드시 라이브러리 require 보다 먼저 실행)
const zlib = require('zlib');
const protocol = require('@mathieuc/tradingview/src/protocol');

const zipParse = protocol.parseCompressed;

protocol.parseCompressed = async (data) => {
  const buf = Buffer.from(data, 'base64');
  if (buf[0] === 0x78) return JSON.parse(zlib.inflateSync(buf).toString());                     // zlib
  if (buf[0] === 0x1f && buf[1] === 0x8b) return JSON.parse(zlib.gunzipSync(buf).toString());   // gzip
  return zipParse(data);                                                                        // zip (구형)
};

module.exports = require('@mathieuc/tradingview');
