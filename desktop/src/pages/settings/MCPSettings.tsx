import { useState, useEffect } from 'react';
import { Icon } from '../../components/Icon';
import './mcp-settings.css';

interface Grant {
  key: string;
  type: 'file' | 'folder';
  file_id?: string;
  file_name?: string;
  folder_id?: string;
  folder_name?: string;
  granted_at: number;
  expires_at: number;
  remaining_seconds: number;
  file_ids?: string[];
}

// TODO: 调用 Tauri API 获取 MCP 可执行文件路径
const EXECUTABLE_PATH = '/Applications/FileSeek.app/Contents/Resources/fileseek-mcp-service';
const MCP_CONFIG = JSON.stringify({ mcpServers: { fileseek: { command: EXECUTABLE_PATH } } }, null, 2);

export default function MCPSettings() {
  // Filled in once the grants API exists (see the TODOs below).
  const [grants] = useState<Grant[]>([]);
  const mcpConfig = MCP_CONFIG;
  const isServiceAvailable = true;
  const [showConfig, setShowConfig] = useState<boolean>(false);

  const loadGrants = async () => {
    try {
      // TODO: 调用 Tauri API 读取 mcp-grants.json
      // const grantsData = await invoke('read_mcp_grants');
      // setGrants(grantsData);
    } catch (error) {
      console.error('加载授权信息失败:', error);
    }
  };

  useEffect(() => {
    loadGrants();

    const interval = setInterval(() => {
      loadGrants();
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const copyConfig = () => {
    navigator.clipboard.writeText(mcpConfig);
    // TODO: 显示 toast 提示
    alert('配置已复制到剪贴板');
  };

  const openConfigGuide = () => {
    // TODO: 打开配置指南文档或外部链接
    window.open('https://docs.fileseek.app/mcp-setup', '_blank');
  };

  const revokeGrant = async (grantKey: string) => {
    try {
      // TODO: 调用 Tauri API 撤销授权
      void grantKey; // await invoke('revoke_mcp_grant', { grantKey });
      loadGrants();
    } catch (error) {
      console.error('撤销授权失败:', error);
    }
  };

  const clearExpired = async () => {
    try {
      // TODO: 调用 Tauri API 清除过期授权
      // const count = await invoke('clear_expired_grants');
      // alert(`已清除 ${count} 个过期授权`);
      loadGrants();
    } catch (error) {
      console.error('清除过期授权失败:', error);
    }
  };

  const clearAll = async () => {
    if (!confirm('确定要清除所有授权吗？此操作不可撤销。')) {
      return;
    }

    try {
      // TODO: 调用 Tauri API 清除所有授权
      // await invoke('clear_all_grants');
      loadGrants();
    } catch (error) {
      console.error('清除所有授权失败:', error);
    }
  };

  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    if (minutes < 1) {
      return '不到 1 分钟';
    } else if (minutes < 60) {
      return `${minutes} 分钟`;
    } else {
      const hours = Math.floor(minutes / 60);
      return `${hours} 小时 ${minutes % 60} 分钟`;
    }
  };

  return (
    <div className="mcp-settings">
      {/* 配置卡片 */}
      <div className="mcp-config-card">
        <div className="mcp-card-header">
          <div className="mcp-card-heading">
            <span className="mcp-card-icon">
              <Icon name="settings" size={19} />
            </span>
            <div>
              <h2>MCP 服务配置</h2>
              <p>让 AI 助手（如 Claude）通过 MCP 协议访问你的文件库</p>
            </div>
          </div>
          <div className="mcp-status-badge">
            {isServiceAvailable ? (
              <span className="mcp-status-indicator mcp-status-ready">
                <span className="mcp-status-dot"></span>
                服务就绪
              </span>
            ) : (
              <span className="mcp-status-indicator mcp-status-unavailable">
                <span className="mcp-status-dot"></span>
                服务不可用
              </span>
            )}
          </div>
        </div>

        <div className="mcp-card-content">
          <div className="mcp-config-actions">
            <button
              className="mcp-action-button mcp-button-primary"
              onClick={copyConfig}
              disabled={!isServiceAvailable}
            >
              <Icon name="copy" size={16} />
              复制配置
            </button>

            <button
              className="mcp-action-button"
              onClick={() => setShowConfig(!showConfig)}
            >
              {showConfig ? '隐藏配置' : '显示配置'}
            </button>

            <button
              className="mcp-link-button"
              onClick={openConfigGuide}
            >
              配置指南
              <Icon name="external" size={14} />
            </button>
          </div>

          {showConfig && (
            <div className="mcp-config-display">
              <pre>{mcpConfig}</pre>
            </div>
          )}
        </div>
      </div>

      {/* 授权卡片 */}
      <div className="mcp-grants-card">
        <div className="mcp-card-header">
          <div className="mcp-card-heading">
            <span className="mcp-card-icon">
              <Icon name="shield" size={19} />
            </span>
            <div>
              <h2>已授权资源</h2>
              <p>管理 AI 助手对文件的访问权限</p>
            </div>
          </div>
          {grants.length > 0 && (
            <div className="mcp-header-actions">
              <button
                className="mcp-text-button"
                onClick={clearExpired}
              >
                清除过期
              </button>
              <button
                className="mcp-text-button mcp-text-danger"
                onClick={clearAll}
              >
                清除全部
              </button>
            </div>
          )}
        </div>

        <div className="mcp-card-content">
          {grants.length === 0 ? (
            <div className="mcp-empty-state">
              <div className="mcp-empty-icon">
                <Icon name="shield" size={32} />
              </div>
              <div className="mcp-empty-text">
                <p className="mcp-empty-title">暂无授权资源</p>
                <p className="mcp-empty-hint">
                  当 AI 助手请求访问文件时，授权后将在此显示
                </p>
              </div>
            </div>
          ) : (
            <div className="mcp-grants-list">
              {grants.map((grant) => (
                <div key={grant.key} className="mcp-grant-item">
                  <div className="mcp-grant-icon">
                    <Icon name={grant.type === 'folder' ? 'folder' : 'document'} size={18} />
                  </div>
                  <div className="mcp-grant-info">
                    <div className="mcp-grant-name">
                      {grant.type === 'folder' ? grant.folder_name : grant.file_name}
                    </div>
                    <div className="mcp-grant-meta">
                      {grant.type === 'folder' && (
                        <span>{grant.file_ids?.length || 0} 个文件</span>
                      )}
                      <span className="mcp-grant-time">
                        剩余 {formatTime(grant.remaining_seconds)}
                      </span>
                    </div>
                  </div>
                  <button
                    className="mcp-grant-revoke"
                    onClick={() => revokeGrant(grant.key)}
                    title="撤销授权"
                  >
                    <Icon name="close" size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
