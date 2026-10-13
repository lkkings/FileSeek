import type { useTranslate } from "../../i18n/useTranslate";
import type { ActivationError, Entitlement, UnlicensedReason } from "../../services/tauri/license";

type Translate = ReturnType<typeof useTranslate>;

export function activationErrorMessage(error: ActivationError, t: Translate): string {
  switch (error.kind) {
    case "empty_key":
      return t("license.errorEmptyKey", "请输入许可证密钥。");
    case "not_found":
      return t("license.errorNotFound", "许可证不存在，请检查密钥是否输入有误。");
    case "activation_limit":
      return error.current !== null && error.max !== null
        ? t("license.errorLimitCounts", "此许可证已在 {current}/{max} 台设备上激活。请在客户门户中释放不再使用的设备。", {
            current: error.current,
            max: error.max,
          })
        : t("license.errorLimit", "此许可证的激活设备数已满。请在客户门户中释放不再使用的设备。");
    case "expired":
      return t("license.errorExpired", "许可证已过期。");
    case "suspended":
      return t("license.errorSuspended", "许可证已暂停。");
    case "revoked":
      return t("license.errorRevoked", "许可证已吊销。");
    case "canceled":
      return t("license.errorCanceled", "许可证已取消。");
    case "locked_out":
      return t("license.errorLockedOut", "尝试次数过多，请稍后再试。");
    case "network":
      return t("license.errorNetwork", "无法连接许可服务器，请检查网络。");
    case "bad_token":
      return t("license.errorBadToken", "许可服务器返回了无效的许可。");
    case "no_device":
      return t("license.errorNoDevice", "无法识别本机，无法激活。");
    case "not_activated":
      return t("license.errorNotActivated", "本机没有已激活的许可。");
    case "server":
    case "io":
    default:
      return t("license.errorServer", "操作失败，请稍后重试。");
  }
}

/** Why the activation screen is showing. */
export function unlicensedMessage(reason: UnlicensedReason | null, t: Translate): string {
  switch (reason) {
    case "invalid":
      return t("license.reasonInvalid", "许可无效，请重新激活。");
    case "revoked":
      return t("license.reasonRevoked", "许可证已失效，请续费或使用其他许可证激活。");
    case "offline_expired":
      return t("license.reasonOffline", "需要联网验证许可。请连接网络后重试。");
    case "no_device":
      return t("license.errorNoDevice", "无法识别本机，无法激活。");
    case "none":
    default:
      return t("license.reasonNone", "尚未激活。输入许可证密钥以开始使用 FileSeek。");
  }
}

function day(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "";
}

/** Settings → License: one line per fact. */
export function licenseFacts(e: Entitlement, t: Translate): string[] {
  const facts = [e.planName ?? (e.licenseId ? t("license.licenseId", "许可 {id}", { id: e.licenseId }) : t("license.licensed", "已激活"))];
  facts.push(
    e.validUntil
      ? t("license.validUntil", "有效期至 {date}", { date: day(e.validUntil) })
      : t("license.perpetual", "有效期：永久"),
  );
  if (e.updatesUntil) facts.push(t("license.updatesUntil", "可更新至 {date} 前发布的版本", { date: day(e.updatesUntil) }));
  if (e.offlineDaysLeft !== null) {
    facts.push(t("license.offlineGrace", "离线中，请在 {n} 天内联网验证", { n: e.offlineDaysLeft }));
  }
  return facts;
}
