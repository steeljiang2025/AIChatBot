import type { JSX, ReactElement } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

interface Props {
  children: ReactElement;
}

export default function RequireAuth({ children }: Props): JSX.Element {
  const isAuthed = useAuthStore((s) => Boolean(s.token));
  const location = useLocation();
  if (!isAuthed) {
    return (
      <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
    );
  }
  return children;
}
