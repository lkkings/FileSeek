import { useState, type FormEvent } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { StorageConnectionResult, StorageLocation, StorageLocationInput, StorageProtocol } from "../types";

interface ConnectionResult {
  locationId: string;
  success: boolean;
  message: string;
}

interface StorageDriveManagerProps {
  drives: StorageLocation[];
  onAddDrive: (drive: StorageLocationInput) => Promise<boolean>;
  onRemoveDrive: (driveId: string) => Promise<void>;
  onTestDrive: (driveId: string) => Promise<StorageConnectionResult>;
  formOpen: boolean;
}

export function StorageDriveManager({
  drives,
  onAddDrive,
  onRemoveDrive,
  onTestDrive,
  formOpen,
}: StorageDriveManagerProps) {
  const t = useTranslate();
  const [connectionResult, setConnectionResult] = useState<ConnectionResult | null>(null);
  const [driveName, setDriveName] = useState("");
  const [driveId, setDriveId] = useState("");
  const [driveError, setDriveError] = useState("");
  const [driveEndpoint, setDriveEndpoint] = useState("");
  const [driveRootPath, setDriveRootPath] = useState("");
  const [driveProtocol, setDriveProtocol] = useState<StorageProtocol>("mounted");
  const [driveAccount, setDriveAccount] = useState("");
  const [drivePassword, setDrivePassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testingDriveId, setTestingDriveId] = useState<string | null>(null);

  const localDrives = drives.filter((drive) => drive.type === "local" || drive.type === "external");
  const nasDrives = drives.filter((drive) => drive.type === "nas");

  const resetDriveForm = () => {
    setDriveName("");
    setDriveId("");
    setDriveEndpoint("");
    setDriveRootPath("");
    setDriveAccount("");
    setDrivePassword("");
    setDriveError("");
  };

  const handleAddDrive = async (event: FormEvent) => {
    event.preventDefault();
    const name = driveName.trim();
    const endpoint = driveEndpoint.trim();
    const rootPath = driveRootPath.trim() || (driveProtocol === "mounted" ? endpoint : "");

    if (!name) {
      setDriveError(t("settings.driveNameRequired", "请输入驱动名称"));
      return;
    }
    if (!endpoint) {
      setDriveError(t("settings.driveEndpointRequired", "请填写连接信息"));
      return;
    }

    try {
      setIsSubmitting(true);
      const input: StorageLocationInput = {
        name,
        protocol: driveProtocol,
        endpoint,
        root_path: rootPath,
        account: driveAccount.trim() || null,
        password: drivePassword || null,
      };
      const identifier = driveId.trim();
      if (identifier) input.id = identifier;
      await onAddDrive(input);
      resetDriveForm();
    } catch (cause) {
      setDriveError(cause instanceof Error ? cause.message : t("settings.storageCreateFailed", "添加存储失败"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveDrive = async (drive: StorageLocation) => {
    setConnectionResult(null);
    try {
      await onRemoveDrive(drive.id);
    } catch (cause) {
      setConnectionResult({
        locationId: drive.id,
        success: false,
        message: cause instanceof Error ? cause.message : t("settings.storageDeleteFailed", "移除存储失败"),
      });
    }
  };

  const handleTestDrive = async (drive: StorageLocation) => {
    setTestingDriveId(drive.id);
    setConnectionResult(null);
    try {
      const result = await onTestDrive(drive.id);
      setConnectionResult({ ...result, locationId: drive.id });
    } catch (cause) {
      setConnectionResult({
        locationId: drive.id,
        success: false,
        message: cause instanceof Error ? cause.message : t("settings.connectionTestFailed", "测试连接失败"),
      });
    } finally {
      setTestingDriveId(null);
    }
  };

  const renderDriveList = (groupDrives: StorageLocation[], emptyMessage: string) => {
    if (groupDrives.length === 0) {
      return <p className="settings-empty">{emptyMessage}</p>;
    }

    return (
      <ul className="settings-drive-list">
        {groupDrives.map((drive) => (
          <li key={drive.id} className="settings-drive-card">
            <div className="settings-drive-card-header">
              <span className="settings-drive-icon">
                <Icon name="nas" size={20} />
              </span>
              <div className="settings-drive-card-info">
                <strong>{drive.name}</strong>
                <span>{drive.account || drive.protocol.toUpperCase()}</span>
              </div>
              <div className="settings-drive-actions">
                {connectionResult?.locationId === drive.id && (
                  <span className="settings-drive-status">
                    {connectionResult.message || (connectionResult.success
                      ? t("settings.connectionSuccess", "连接正常")
                      : t("settings.connectionFailed", "连接失败"))}
                  </span>
                )}
                <button
                  type="button"
                  className="settings-drive-test"
                  disabled={testingDriveId === drive.id}
                  onClick={() => handleTestDrive(drive)}
                >
                  {t("settings.testConnection", "测试连接")}
                </button>
                <button
                  type="button"
                  className="settings-drive-remove"
                  disabled={drive.is_system}
                  onClick={() => handleRemoveDrive(drive)}
                  aria-label={`${t("common.remove", "移除")} ${drive.name}`}
                  title={drive.is_system
                    ? t("settings.systemStorageProtected", "系统存储不可移除")
                    : t("settings.storageDeletionWarning", "移除后已绑定文件将标记为不可获取")}
                >
                  <Icon name="close" size={14} />
                </button>
              </div>
            </div>
            <div className="settings-drive-card-meta">
              <code>{drive.endpoint}</code>
            </div>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="settings-storage-manager">
      {formOpen && (
        <form className="settings-drive-form" onSubmit={handleAddDrive}>
          <div className="settings-drive-fields">
            <div className="settings-field">
              <label htmlFor="drive-name">{t("settings.driveName", "驱动名称")}</label>
              <input
                id="drive-name"
                value={driveName}
                onChange={(event) => setDriveName(event.target.value)}
              />
            </div>

            <div className="settings-field">
              <label htmlFor="nas-protocol">{t("settings.nasProtocol", "协议")}</label>
              <select
                id="nas-protocol"
                value={driveProtocol}
                onChange={(event) => setDriveProtocol(event.target.value as StorageProtocol)}
              >
                <option value="mounted">已挂载路径</option>
                <option value="smb">SMB</option>
                <option value="nfs">NFS</option>
                <option value="webdav">WebDAV</option>
              </select>
            </div>
            <div className="settings-field">
              <label htmlFor="drive-id">{t("settings.driveId", "存储标识")}</label>
              <input
                id="drive-id"
                value={driveId}
                onChange={(event) => setDriveId(event.target.value)}
                placeholder="nas1"
                autoComplete="off"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="drive-endpoint">{t("settings.nasHost", "主机地址")}</label>
              <input
                id="drive-endpoint"
                value={driveEndpoint}
                onChange={(event) => setDriveEndpoint(event.target.value)}
                placeholder={driveProtocol === "mounted" ? "/Volumes/nas1" : "smb://nas.local/media"}
              />
            </div>
            <div className="settings-field">
              <label htmlFor="drive-root-path">{t("settings.nasSharePath", "挂载路径")}</label>
              <input
                id="drive-root-path"
                value={driveRootPath}
                onChange={(event) => setDriveRootPath(event.target.value)}
                placeholder="/Volumes/nas1"
                disabled={driveProtocol !== "mounted"}
              />
            </div>
            <div className="settings-field">
              <label htmlFor="nas-username">{t("settings.nasUsername", "用户名")}</label>
              <input
                id="nas-username"
                value={driveAccount}
                onChange={(event) => setDriveAccount(event.target.value)}
                autoComplete="off"
              />
            </div>
            <div className="settings-field">
              <label htmlFor="nas-password">{t("settings.nasPassword", "密码")}</label>
              <input
                id="nas-password"
                type="password"
                value={drivePassword}
                onChange={(event) => setDrivePassword(event.target.value)}
                autoComplete="new-password"
              />
            </div>
          </div>

          {driveError && <p className="settings-inline-error">{driveError}</p>}
          <button className="settings-submit" type="submit" disabled={isSubmitting}>
            <Icon name="plus" size={16} />
            <span>{t("settings.addDrive", "添加驱动")}</span>
          </button>
        </form>
      )}

      <div className="settings-storage-groups">
        <section className="settings-storage-group">
          <h3>{t("settings.localStorage", "本地存储")}</h3>
          {renderDriveList(localDrives, t("settings.noLocalStorage", "未找到本地存储配置。"))}
        </section>
        <section className="settings-storage-group">
          <h3>{t("settings.nasStorage", "NAS 存储")}</h3>
          {renderDriveList(nasDrives, t("settings.noDrives", "暂未配置存储驱动。"))}
        </section>
      </div>
    </div>
  );
}
