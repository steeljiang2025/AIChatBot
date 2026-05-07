import { Navigate, Route, Routes } from "react-router-dom";
import HealthCheck from "@/pages/HealthCheck";
import LoginPage from "@/pages/Login";
import Workspace from "@/pages/Workspace";
import RequireAuth from "@/components/RequireAuth";

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/workspace" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/workspace"
        element={
          <RequireAuth>
            <Workspace />
          </RequireAuth>
        }
      />
      <Route path="/health" element={<HealthCheck />} />
      <Route path="*" element={<Navigate to="/workspace" replace />} />
    </Routes>
  );
}
