/** identity 模块类型 */

export type UserOut = {
  id: string;
  email: string;
  display_name: string;
  status: string;
  created_at: string;
};

export type TokenOut = {
  access_token: string;
  token_type: string;
  user: UserOut;
};

export type WorkspaceOut = {
  id: string;
  name: string;
  created_by: string;
  role: string | null;
  created_at: string;
  updated_at: string;
};

export type UserRegisterInput = {
  email: string;
  password: string;
  display_name: string;
};

export type UserLoginInput = {
  email: string;
  password: string;
};

export type WorkspaceCreateInput = {
  name: string;
};

export type WorkspaceUpdateInput = {
  name?: string;
};
