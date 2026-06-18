import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminAccountsPanel } from "@/components/admin-accounts-panel";
import type { AccountDTO } from "@/lib/agent";
import { renderWithProviders } from "../helpers/render-with-providers";

const ACCOUNTS: AccountDTO[] = [
  account(1, "nguyen-son", "Nguyễn Sơn", true),
  account(2, "Nguy?n S?n", "", false),
  account(3, "ngoc-quyen", "Ngọc Quyên", true),
  account(4, "Gia Ki?t", "", false),
  account(5, "testops", "", true, "admin")
];

describe("AdminAccountsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("hides disabled legacy accounts by default and keeps active member names readable", () => {
    renderPanel();

    expect(screen.getByText("Nguyễn Sơn")).toBeInTheDocument();
    expect(screen.getByText("Ngọc Quyên")).toBeInTheDocument();
    expect(screen.queryByText("Nguy?n S?n")).not.toBeInTheDocument();
    expect(screen.queryByText("Gia Ki?t")).not.toBeInTheDocument();
  });

  it("reveals disabled accounts only when the admin asks for them", async () => {
    renderPanel();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /Hiện vô hiệu/i }));

    expect(screen.getByText("Nguy?n S?n")).toBeInTheDocument();
    expect(screen.getByText("Gia Ki?t")).toBeInTheDocument();
  });

  it("keeps owner assignment limited to active user accounts", () => {
    renderPanel();
    const ownerSelect = screen.getByLabelText(/Gán chủ sở hữu/i);

    expect(ownerSelect).toHaveTextContent("Nguyễn Sơn (nguyen-son)");
    expect(ownerSelect).toHaveTextContent("Ngọc Quyên (ngoc-quyen)");
    expect(ownerSelect).not.toHaveTextContent("Nguy?n S?n");
    expect(ownerSelect).not.toHaveTextContent("testops");
  });
});

function renderPanel() {
  return renderWithProviders(
    <AdminAccountsPanel
      accounts={ACCOUNTS}
      busy={false}
      chatAnswer={null}
      chatQuestion=""
      createDisplayName=""
      createPassword=""
      createRole="user"
      createUsername=""
      knowledgeCatalog={null}
      knowledgeEvaluation={null}
      resetPassword=""
      selectedOwner=""
      onAskChat={vi.fn()}
      onBackfillOwner={vi.fn()}
      onChatQuestionChange={vi.fn()}
      onCreateAccount={vi.fn()}
      onCreateDisplayNameChange={vi.fn()}
      onCreatePasswordChange={vi.fn()}
      onCreateRoleChange={vi.fn()}
      onCreateUsernameChange={vi.fn()}
      onEvaluateKnowledge={vi.fn()}
      onPatchKnowledge={vi.fn()}
      onRefresh={vi.fn()}
      onReloadKnowledge={vi.fn()}
      onResetPassword={vi.fn()}
      onResetPasswordChange={vi.fn()}
      onSelectedOwnerChange={vi.fn()}
      onToggleActive={vi.fn()}
      onUpsertKnowledge={vi.fn()}
    />
  );
}

function account(
  id: number,
  username: string,
  displayName: string,
  active: boolean,
  role: AccountDTO["role"] = "user"
): AccountDTO {
  return {
    id,
    username,
    display_name: displayName,
    role,
    is_active: active,
    password_default: false,
    created_at: "2026-06-18T00:00:00+00:00",
    last_login_at: null
  };
}
