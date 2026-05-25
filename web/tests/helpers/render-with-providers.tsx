import type { ReactElement } from "react";
import { render, type RenderOptions } from "@testing-library/react";

/**
 * A thin wrapper around @testing-library/react's render().
 * The components under test in this app are presentational and receive
 * all data through props — no context providers are needed.
 *
 * When future components use AuthContext or OperationsContext, extend
 * the Wrapper here with the appropriate Provider wrappings.
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return render(ui, options);
}
