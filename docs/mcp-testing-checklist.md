# MCP 服务测试清单

本文档列出了需要在实际环境中进行的测试项目。

## 前置条件

- [ ] Backend 已启动并运行在默认端口
- [ ] Desktop 应用已构建并运行
- [ ] MCP Service 已打包成可执行文件
- [ ] Claude Desktop 或其他 MCP 客户端已安装

## 5. MCP Server 集成测试

### 5.1 端到端测试：基础功能

- [ ] 启动隔离的 Backend 实例
- [ ] 启动 MCP Service (`python -m mcp-service`)
- [ ] 验证 MCP Service 成功连接到 Backend
- [ ] 测试 `list_folders` 工具返回正确数据
- [ ] 测试 `search_files` 工具返回搜索结果

**预期结果**：所有工具返回正确的 JSON 格式数据，无异常退出

### 5.2 授权流程测试

- [ ] 调用 `read_file` 读取未授权文件
- [ ] 验证返回权限错误和授权选项
- [ ] 调用 `grant_file_access` 授权文件
- [ ] 验证授权成功返回
- [ ] 再次调用 `read_file` 
- [ ] 验证成功返回文件内容
- [ ] 等待授权过期（或手动修改 `mcp-grants.json`）
- [ ] 再次调用 `read_file`
- [ ] 验证返回权限过期错误

**预期结果**：权限机制正常工作，过期授权被正确识别

### 5.3 动态 Token 刷新测试

- [ ] 记录当前 Backend 的 token（从 `connection.json`）
- [ ] 重启 Backend（生成新 token）
- [ ] 验证 `connection.json` 中的 token 已更新
- [ ] 调用 MCP Service 的任意工具
- [ ] 验证 MCP Service 自动使用新 token
- [ ] 验证工具调用成功

**预期结果**：MCP Service 自动适配新 token，无需重启

### 5.4 授权持久化测试

- [ ] 授权一个文件（`grant_file_access`）
- [ ] 验证 `mcp-grants.json` 包含授权记录
- [ ] 停止 MCP Service
- [ ] 重新启动 MCP Service
- [ ] 验证启动日志显示"已加载 X 个有效授权"
- [ ] 调用 `read_file` 读取之前授权的文件
- [ ] 验证无需重新授权即可读取

**预期结果**：授权跨 MCP Service 重启保留

## 10. 端到端验证

### 10.1 Claude Desktop：列出文件夹

- [ ] 配置 Claude Desktop（按 `docs/mcp-setup-guide.md`）
- [ ] 重启 Claude Desktop
- [ ] 在对话中输入："列出我的文件夹"
- [ ] 验证 Claude 返回文件夹列表
- [ ] 验证列表包含正确的文件夹名称和文件数量

**预期结果**：Claude 正确显示 FileSeek 的文件夹

### 10.2 Claude Desktop：搜索文件

- [ ] 在 Claude 中输入："搜索包含'报告'的文件"
- [ ] 验证 Claude 返回搜索结果
- [ ] 验证结果包含文件名、路径、文件类型等信息
- [ ] 尝试带过滤条件的搜索："在工作文档文件夹中搜索 PDF 文件"
- [ ] 验证返回结果符合过滤条件

**预期结果**：搜索功能正常，结果准确

### 10.3 Claude Desktop：读取未授权文件

- [ ] 在 Claude 中输入："读取文件 [某个文件名]"
- [ ] 验证 Claude 收到权限错误
- [ ] 验证 Claude 理解错误并询问用户是否授权
- [ ] 验证提示中包含文件信息和授权选项

**预期结果**：Claude 正确理解权限错误，向用户解释并询问

### 10.4 Claude Desktop：授权后读取

- [ ] 用户确认授权（Claude 调用 `grant_file_access`）
- [ ] 验证 Claude 提示"已授权"
- [ ] Claude 再次调用 `read_file`
- [ ] 验证 Claude 成功获取文件内容
- [ ] 验证内容正确（文档文本或图片描述）

**预期结果**：授权流程顺畅，文件内容正确返回

### 10.5 Backend 重启适配

- [ ] 在 Claude 对话过程中，重启 FileSeek Backend
- [ ] 等待 Backend 完全启动
- [ ] 在 Claude 中执行任意操作（如搜索）
- [ ] 验证 MCP Service 自动适配新 token
- [ ] 验证操作成功，无需重启 Claude Desktop

**预期结果**：Backend 重启不影响 MCP 服务可用性

### 10.6 MCP Service 重启保留授权

- [ ] 授权一些文件/文件夹
- [ ] 查看 Desktop 的 MCP 设置页面，验证显示授权列表
- [ ] 重启 Claude Desktop（会重启 MCP Service）
- [ ] 等待 Claude 完全启动
- [ ] 尝试读取之前授权的文件
- [ ] 验证无需重新授权即可读取
- [ ] 在 Desktop 的 MCP 设置页面验证授权列表仍然存在

**预期结果**：授权跨 MCP Service 重启保留

## 额外测试项

### 图片文件读取

- [ ] 搜索一个图片文件
- [ ] 授权并读取
- [ ] 验证返回 Base64 编码的图片数据
- [ ] 验证 MIME 类型正确

### 视频文件拒绝

- [ ] 搜索一个视频文件
- [ ] 授权并尝试读取
- [ ] 验证返回"不支持视频文件"错误

### 文档分页读取

- [ ] 找一个多页 PDF 文档
- [ ] 授权文件
- [ ] 读取特定页：`read_file(file_id=..., page=5)`
- [ ] 验证只返回第 5 页的内容
- [ ] 读取 chunk 范围：`read_file(file_id=..., chunk_start=10, chunk_end=20)`
- [ ] 验证只返回指定范围的 chunks

### Desktop MCP 设置页面

- [ ] 打开 FileSeek Desktop
- [ ] 进入设置 → MCP 服务
- [ ] 验证配置 JSON 正确显示
- [ ] 点击"复制配置"，验证剪贴板内容
- [ ] 点击"打开 Claude 配置目录"，验证打开正确目录
- [ ] 授权一些文件后，验证授权列表正确显示
- [ ] 验证剩余时间每分钟更新
- [ ] 点击"撤销"，验证授权被移除
- [ ] 点击"清除已过期"，验证只清除过期授权
- [ ] 点击"清除所有授权"，验证弹出确认对话框

## 测试通过标准

- ✅ 所有功能按预期工作
- ✅ 无未处理的异常或崩溃
- ✅ 错误信息清晰易懂
- ✅ UI 响应流畅
- ✅ 权限机制可靠
- ✅ 文档准确无误

## 问题记录

在测试过程中发现的问题记录在此：

| 测试项 | 问题描述 | 严重程度 | 状态 |
|--------|----------|----------|------|
| -      | -        | -        | -    |

---

**测试日期**：_________  
**测试人员**：_________  
**环境**：macOS / Windows / Linux
