// 트레이딩뷰 계정으로 로그인해 SESSION / SIGNATURE 쿠키 발급
// 사용: npm run login -- <이메일> <비밀번호>
// 2FA 계정은 실패할 수 있음 → 브라우저 쿠키(sessionid, sessionid_sign)를 직접 복사
const TradingView = require('@mathieuc/tradingview');

const [username, password] = process.argv.slice(2);
if (!username || !password) {
  console.error('사용법: npm run login -- <이메일> <비밀번호>');
  process.exit(1);
}

TradingView.loginUser(username, password, false)
  .then((user) => {
    console.log('로그인 성공:', user.username);
    console.log('.env 에 아래 값을 넣으세요');
    console.log(`SESSION=${user.session}`);
    console.log(`SIGNATURE=${user.signature}`);
  })
  .catch((err) => console.error('로그인 실패:', err.message));
