#!/bin/bash
# MCP Server 打包脚本

set -e

echo "开始打包 FileSeek MCP Service..."

# 进入 MCP Service 目录
cd "$(dirname "$0")"

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "使用 Python 版本: $python_version"

# 安装依赖
echo "安装依赖..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# 使用 PyInstaller 打包
echo "使用 PyInstaller 打包..."
pyinstaller build.spec

# 检查输出文件
if [ -f "dist/fileseek-mcp-service" ]; then
    echo "✅ 打包成功！"
    echo "可执行文件位置: $(pwd)/dist/fileseek-mcp-service"

    # 显示文件大小
    size=$(du -h dist/fileseek-mcp-service | cut -f1)
    echo "文件大小: $size"

    # 检查大小是否超过 50MB
    size_mb=$(du -m dist/fileseek-mcp-service | cut -f1)
    if [ "$size_mb" -gt 50 ]; then
        echo "⚠️  警告: 文件大小超过 50MB ($size_mb MB)"
    fi
else
    echo "❌ 打包失败"
    exit 1
fi
