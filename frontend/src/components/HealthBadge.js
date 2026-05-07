import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Tag, Tooltip } from "antd";
import { CheckCircleFilled, CloseCircleFilled, LoadingOutlined } from "@ant-design/icons";
export default function HealthBadge({ label, status, hint }) {
    const tag = status === "loading" ? (_jsxs(Tag, { icon: _jsx(LoadingOutlined, {}), color: "processing", children: [label, " \u00B7 \u68C0\u6D4B\u4E2D"] })) : status === "ok" ? (_jsxs(Tag, { icon: _jsx(CheckCircleFilled, {}), color: "success", children: [label, " \u00B7 OK"] })) : (_jsxs(Tag, { icon: _jsx(CloseCircleFilled, {}), color: "error", children: [label, " \u00B7 \u5F02\u5E38"] }));
    return hint ? _jsx(Tooltip, { title: hint, children: tag }) : tag;
}
