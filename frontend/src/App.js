import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Layout, Typography } from "antd";
import { Navigate, Route, Routes } from "react-router-dom";
import HealthCheck from "./pages/HealthCheck";
const { Header, Content, Footer } = Layout;
function App() {
    return (_jsxs(Layout, { style: { minHeight: "100vh" }, children: [_jsx(Header, { style: { background: "#001529", display: "flex", alignItems: "center" }, children: _jsx(Typography.Title, { level: 4, style: { color: "white", margin: 0 }, children: "AIChatBot \u00B7 \u667A\u80FD\u6570\u636E\u5206\u6790\u52A9\u7406" }) }), _jsx(Content, { style: { padding: "24px", maxWidth: 960, width: "100%", margin: "0 auto" }, children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/health", replace: true }) }), _jsx(Route, { path: "/health", element: _jsx(HealthCheck, {}) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/health", replace: true }) })] }) }), _jsx(Footer, { style: { textAlign: "center", color: "#888" }, children: "Phase 1 \u00B7 Skeleton \u2014 \u540E\u7EED Phase 2 \u5C06\u5207\u6362\u5230\u4E09\u680F Workspace" })] }));
}
export default App;
