/* اجرای سرویس وب روی همین رایانه (برای تست قبل از دیپلوی Vercel).
 *
 *   cd vercel && node dev-server.js
 *   → http://127.0.0.1:8000
 *
 * اگر SITE_PASSWORD را ندهید، یکی تصادفی ساخته و چاپ می‌کند (فقط برای تست محلی).
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = __dirname;
const PORT = Number(process.env.PORT || 8000);
const PUB = path.join(ROOT, "public");

// env باید قبل از load شدن هندلر تنظیم شود (آن در لحظه require می‌خواند)
process.env.SITE_PASSWORD ||= crypto.randomBytes(9).toString("base64url");
process.env.APP_SECRET ||= crypto.randomBytes(24).toString("base64url");
process.env.DATA_URL ||= `http://127.0.0.1:${PORT}/data/stores.json`;

const handler = require(path.join(ROOT, "api", "index.js"));

const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8" };

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const file = path.join(PUB, url.pathname === "/" ? "index.html" : url.pathname.replace(/^\/+/, ""));
  if (!url.pathname.startsWith("/api/") && file.startsWith(PUB) && fs.existsSync(file) && fs.statSync(file).isFile()) {
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream" });
    return res.end(fs.readFileSync(file));
  }
  return handler(req, res);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`🏪 فروشگاه‌یاب محلی: http://127.0.0.1:${PORT}`);
  console.log(`   رمز ورود: ${process.env.SITE_PASSWORD}`);
  console.log(`   APP_SECRET: ${process.env.APP_SECRET}`);
  console.log("   (فقط برای تست محلی؛ در Vercel مقدار خودتان را بگذارید)");
});
