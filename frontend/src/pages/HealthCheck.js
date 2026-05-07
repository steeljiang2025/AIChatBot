import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Descriptions, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { fetchHealth } from "../api/health";
import HealthBadge from "../components/HealthBadge";
const { Paragraph, Text } = Typography;
const initial = { loading: true };
export default function HealthCheck() {
    const [state, setState] = useState(initial);
    const load = useCallback(async () => {
        setState({ loading: true });
        try {
            const data = await fetchHealth();
            setState({ loading: false, data });
        }
        catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            setState({ loading: false, error: msg });
        }
    }, []);
    useEffect(() => {
        void load();
    }, [load]);
    const overall = state.loading
        ? "loading"
        : state.data?.status === "ok"
            ? "ok"
            : "down";
    const meta = state.loading
        ? "loading"
        : state.data?.db.meta === "ok"
            ? "ok"
            : "down";
    const biz = state.loading
        ? "loading"
        : state.data?.db.biz === "ok"
            ? "ok"
            : "down";
    return (_jsxs(Space, { direction: "vertical", size: "large", style: { width: "100%" }, children: [_jsxs(Card, { title: "\u540E\u7AEF\u8FDE\u63A5 / \u6570\u636E\u5E93\u63A2\u9488", extra: _jsx(Button, { icon: _jsx(ReloadOutlined, {}), onClick: load, loading: state.loading, children: "\u91CD\u65B0\u68C0\u6D4B" }), children: [_jsxs(Space, { size: "middle", wrap: true, children: [_jsx(HealthBadge, { label: "\u540E\u7AEF", status: overall, hint: "GET /api/health" }), _jsx(HealthBadge, { label: "meta DB", status: meta, hint: "\u5E94\u7528\u5143\u6570\u636E\u5E93" }), _jsx(HealthBadge, { label: "biz DB", status: biz, hint: "\u4E1A\u52A1\u5E93\uFF08\u53EA\u8BFB\u8D26\u53F7\uFF09" })] }), state.error && (_jsx(Alert, { style: { marginTop: 16 }, type: "error", showIcon: true, message: "\u8BF7\u6C42\u5931\u8D25", description: state.error })), state.data && (_jsxs(Descriptions, { column: 1, style: { marginTop: 24 }, size: "small", bordered: true, children: [_jsx(Descriptions.Item, { label: "\u7248\u672C", children: _jsx(Text, { code: true, children: state.data.version }) }), _jsx(Descriptions.Item, { label: "\u73AF\u5883", children: state.data.env }), _jsx(Descriptions.Item, { label: "\u6574\u4F53\u72B6\u6001", children: state.data.status })] }))] }), _jsx(Card, { title: "\u4E0B\u4E00\u6B65", children: _jsxs(Paragraph, { children: ["\u9AA8\u67B6\u5DF2\u5C31\u7EEA\u3002Phase 2 \u5C06\u628A\u8FD9\u9875\u66FF\u6362\u4E3A\u4E09\u680F Workspace\uFF08\u804A\u5929 + \u56FE\u8868 + \u4F1A\u8BDD\u5217\u8868\uFF09\uFF1BPhase 3 \u5C06\u63A5\u5165\u771F\u5B9E\u7684", " ", _jsx(Text, { code: true, children: "/auth" }), "\u3001", _jsx(Text, { code: true, children: "/sessions" }), "\u3001", _jsx(Text, { code: true, children: "/chat/stream" }), " \u63A5\u53E3\u3002"] }) })] }));
}
