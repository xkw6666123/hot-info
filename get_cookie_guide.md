# 获取完整抖音 Cookie 指南

## 方法 1️⃣：Network 标签（推荐）

1. 打开 https://www.douyin.com/ 确保已登录
2. 按 F12 → 点击 **Network**（网络）标签
3. 按 **F5** 刷新页面
4. 等待页面加载完成，看左侧列表
5. **关键点**：在过滤器框里输入 `douyin`，只显示 douyin 相关的请求
6. 点击任意一个 `www.douyin.com` 开头的请求
7. 右侧面板 → **Headers** 标签 → 往下滑找到 **Request Headers**
8. 找到 **Cookie:** 那一行，**右键 → Copy value**

## 方法 2️⃣：更简单 - 直接复制 Network 日志

1. F12 → Network 标签
2. F5 刷新
3. 在任意请求上 **右键 → Copy → Copy as cURL (bash)**
4. 把复制的内容粘贴到任意文本编辑器
5. 找到 `-H 'cookie: ...'` 那一部分，复制引号里的内容

## 方法 3️⃣：用我帮你写的脚本

如果上面方法找不到，运行这个脚本（它会用 Playwright 打开抖音并帮你提取）：

```bash
cd /c/Users/Kevin/WorkBuddy/2026-05-08-task-5/hot-info
python get_cookie_via_playwright.py
```

然后你登录，它会自动保存 Cookie 到文件。

---
如果你还是找不到，请截图 Network 标签的内容给我，我帮你看具体是哪个请求。
