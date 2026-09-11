/** 登录表单字段 / 第三项凭证 / 登录流程状态。 */

export interface LoginFieldInfo {
  role: "username" | "password" | "otp" | "unknown";
  selector: string;
  tag?: string;
  type?: string;
  name?: string;
  id?: string;
  label?: string;
  placeholder?: string;
  autocomplete?: string;
  required?: boolean;
}

export interface LoginFormPayload {
  url: string;
  is_login_page: boolean;
  fields: LoginFieldInfo[];
  submit: LoginFieldInfo | null;
}

/** 附加登录信息（第三项）相对账号/密码槽位的落位（由登录页 DOM 序派生） */
export type ExtraPlacement = "before" | "between" | "after";

/** 可作第三项的字段：LoginFieldInfo + DOM 序下标 + 落位 */
export interface ExtraCandidate extends LoginFieldInfo {
  /** 在 login_form.fields（DOM 文档序）中的下标 */
  order: number;
  /** 相对账号/密码槽位的落位 */
  placement: ExtraPlacement;
}

/** 保存时从当前页捕获的第三项字段特征（供 03 autofill 匹配） */
export interface MatchHints {
  name?: string;
  id?: string;
  label?: string;
  placeholder?: string;
}

/** 附加登录信息（第三项）；无 extra 时传 null，不传空对象 */
export interface ExtraCredential {
  field_label: string;
  value: string;
  match_hints?: MatchHints | null;
}

/** POST /api/credentials 保存请求体 */
export interface LoginCredentialSpec {
  site?: string | null;
  url?: string | null;
  username: string;
  password: string;
  extra?: ExtraCredential | null;
}

/** POST /api/credentials/site-status 请求体 */
export interface SiteStatusRequest {
  url: string;
}

/** 状态响应（非敏感：不含 username/password/extra.value） */
export interface CredentialStatus {
  site: string;
  configured: boolean;
  extra_field_label?: string | null;
  site_label?: string;
}

/** 登录流程状态（autofill 服务构造，SSE login_flow_status 事件；全 snake_case、非敏感） */
export interface LoginFlowStatus {
  site: string;
  login_form_detected: boolean;
  configured: boolean;
  username_filled: boolean;
  password_filled: boolean;
  extra_required: boolean;
  extra_filled: boolean;
  needs_otp: boolean;
  manual_otp_guided: boolean;
  fill_ok: boolean;
  fill_error: string;
}

/** SSE login_flow_status 事件：LoginFlowStatus + 事件信封 */
export interface LoginFlowStatusEvent extends LoginFlowStatus {
  type: "login_flow_status";
  run_id: string;
  timestamp: string;
}
