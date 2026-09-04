import { request } from "./core";
import type {
  CredentialStatus,
  LoginCredentialSpec,
  SiteStatusRequest,
} from "../types";

/** 查询站点凭证状态（configured 布尔 + 附加字段名，非敏感） */
export async function fetchCredentialStatus(url: string): Promise<CredentialStatus> {
  const body: SiteStatusRequest = { url };
  return request<CredentialStatus>("/credentials/site-status", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** 保存（幂等覆盖）站点凭证到系统密钥；返回非敏感状态（configured=true） */
export async function saveCredentials(req: LoginCredentialSpec): Promise<CredentialStatus> {
  return request<CredentialStatus>("/credentials", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

/** 删除站点凭证（幂等，不存在也 ok） */
export async function deleteCredentials(site: string): Promise<void> {
  await request(`/credentials/${encodeURIComponent(site)}`, { method: "DELETE" });
}
