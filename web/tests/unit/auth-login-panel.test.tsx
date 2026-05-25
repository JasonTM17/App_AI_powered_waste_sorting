import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthLoginPanel } from "@/components/auth-login-panel";
import { renderWithProviders } from "../helpers/render-with-providers";

function setup(overrides?: {
  error?: string;
  password?: string;
  pending?: boolean;
  sessionMessage?: string;
  showPassword?: boolean;
  username?: string;
  onPasswordChange?: (value: string) => void;
  onShowPasswordChange?: (value: boolean) => void;
  onSubmit?: () => void;
  onUsernameChange?: (value: string) => void;
}) {
  const props = {
    error: "",
    password: "",
    pending: false,
    sessionMessage: "",
    showPassword: false,
    username: "",
    onPasswordChange: vi.fn(),
    onShowPasswordChange: vi.fn(),
    onSubmit: vi.fn(),
    onUsernameChange: vi.fn(),
    ...overrides
  };
  const result = renderWithProviders(<AuthLoginPanel {...props} />);
  return { props, ...result };
}

describe("AuthLoginPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders username and password inputs", () => {
    setup();
    expect(screen.getByPlaceholderText(/admin hoặc user/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/nhập mật khẩu/i)).toBeInTheDocument();
  });

  it("calls onUsernameChange when username is typed", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/admin hoặc user/i), "test-user");
    expect(props.onUsernameChange).toHaveBeenCalled();
  });

  it("calls onPasswordChange when password is typed", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText(/nhập mật khẩu/i), "test-password");
    expect(props.onPasswordChange).toHaveBeenCalled();
  });

  it("displays error message when error prop is set", () => {
    setup({ error: "Sai tài khoản hoặc mật khẩu" });
    expect(screen.getByRole("alert")).toHaveTextContent("Sai tài khoản hoặc mật khẩu");
  });

  it("applies error class to password wrapper when error is set", () => {
    setup({ error: "Invalid" });
    const passwordInput = screen.getByPlaceholderText(/nhập mật khẩu/i);
    expect(passwordInput.closest(".auth-input-wrap")).toHaveClass("error");
  });

  it("disables submit button and shows pending state", () => {
    setup({ pending: true });
    expect(screen.getByRole("button", { name: /đang đăng nhập/i })).toBeDisabled();
  });

  it("toggles password visibility when eye button is clicked", async () => {
    const { props } = setup({ showPassword: false });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /hiện mật khẩu/i }));
    expect(props.onShowPasswordChange).toHaveBeenCalledWith(true);
  });

  it("auto-focuses the username input on mount", async () => {
    setup();
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/admin hoặc user/i)).toHaveFocus();
    });
  });
});
