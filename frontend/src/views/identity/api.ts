/** identity 模块 API；须经 shared/api-client，禁止直接 fetch。 */
import {
  deleteJson,
  getJson,
  patchJson,
  postJson,
} from "@/shared/api-client";
import type {
  TokenOut,
  UserLoginInput,
  UserOut,
  UserRegisterInput,
  WorkspaceCreateInput,
  WorkspaceOut,
  WorkspaceUpdateInput,
} from "./types";

export function register(data: UserRegisterInput): Promise<UserOut> {
  return postJson<UserOut>("v1/auth/register", data);
}

export function login(data: UserLoginInput): Promise<TokenOut> {
  return postJson<TokenOut>("v1/auth/login", data);
}

export function listWorkspaces(): Promise<WorkspaceOut[]> {
  return getJson<WorkspaceOut[]>("v1/workspaces");
}

export function createWorkspace(
  data: WorkspaceCreateInput,
): Promise<WorkspaceOut> {
  return postJson<WorkspaceOut>("v1/workspaces", data);
}

export function updateWorkspace(
  id: string,
  data: WorkspaceUpdateInput,
): Promise<WorkspaceOut> {
  return patchJson<WorkspaceOut>(`v1/workspaces/${id}`, data);
}

export function deleteWorkspace(id: string): Promise<null> {
  return deleteJson<null>(`v1/workspaces/${id}`);
}
