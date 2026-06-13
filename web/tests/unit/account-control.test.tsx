import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AccountControl } from "@/components/account-control";
import type { AuthMe } from "@/lib/agent";
import { renderWithProviders } from "../helpers/render-with-providers";

const USER_AUTH: AuthMe = {
  role: "user",
  capabilities: ["view_dashboard"],
  auth_required: false,
  account_id: 1,
  username: "test-user",
  display_name: "",
  token_source: "session",
  password_default: false
};

const ADMIN_AUTH: AuthMe = {
  role: "admin",
  capabilities: ["admin"],
  auth_required: false,
  account_id: 2,
  username: "test-admin",
  display_name: "",
  token_source: "session",
  password_default: false
};

function setup(overrides?: { auth?: AuthMe | null; busy?: boolean; onLogout?: () => void }) {
  const props = {
    auth: USER_AUTH,
    busy: false,
    onLogout: vi.fn(),
    ...overrides
  };
  const result = renderWithProviders(<AccountControl {...props} />);
  return { props, ...result };
}

describe("AccountControl", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows user role label for non-admin accounts", () => {
    const { container } = setup({ auth: USER_AUTH });
    expect(screen.getByText("Test User")).toBeInTheDocument();
    expect(screen.getByText("Tài khoản người dùng")).toBeInTheDocument();
    expect(container.querySelector(".account-avatar-frame")).toHaveTextContent("TU");
  });

  it("prefers display_name for member accounts", () => {
    const { container } = setup({ auth: { ...USER_AUTH, username: "nguyen-son", display_name: "Nguyễn Sơn" } });
    expect(screen.getByText("Nguyễn Sơn")).toBeInTheDocument();
    expect(container.querySelector(".account-avatar-frame.generated-avatar")).toHaveTextContent("NS");
  });

  it("uses a professional display name for the generic local user account", () => {
    setup({ auth: { ...USER_AUTH, username: "user" } });
    expect(screen.getByText("Thành viên EcoSort")).toBeInTheDocument();
  });

  it("shows admin role label for admin accounts", () => {
    setup({ auth: ADMIN_AUTH });
    expect(screen.getByText("Quản trị viên")).toBeInTheDocument();
  });

  it("calls onLogout when logout button is clicked", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /đăng xuất/i }));
    expect(props.onLogout).toHaveBeenCalledTimes(1);
  });

  it("disables logout button when busy", () => {
    setup({ busy: true });
    expect(screen.getByRole("button", { name: /đăng xuất/i })).toBeDisabled();
  });

  it("shows default password warning when password_default is true", () => {
    setup({ auth: { ...USER_AUTH, password_default: true } });
    expect(screen.getByText("Mật khẩu mặc định")).toBeInTheDocument();
  });

  it("does not show default password warning for non-default passwords", () => {
    setup({ auth: { ...USER_AUTH, password_default: false } });
    expect(screen.queryByText("Mật khẩu mặc định")).not.toBeInTheDocument();
  });
});
