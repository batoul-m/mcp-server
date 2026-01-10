const { spawn } = require("child_process");

const child = spawn(
  "/home/user/Desktop/vsCode/Harri training/harri_web_mcp/.venv/bin/python",
  ["/home/user/Desktop/vsCode/Harri training/harri_web_mcp/server.py"],
  {
    stdio: ["pipe", "pipe", "pipe"], // 🔑 IMPORTANT
    cwd: __dirname,
    env: process.env,
  }
);

child.on("exit", (code) => {
  console.error("MCP server exited with code", code);
});
