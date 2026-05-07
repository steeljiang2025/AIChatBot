import { Layout, Typography } from "antd";
import { Navigate, Route, Routes } from "react-router-dom";

import HealthCheck from "./pages/HealthCheck";

const { Header, Content, Footer } = Layout;

function App() {
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header style={{ background: "#001529", display: "flex", alignItems: "center" }}>
        <Typography.Title level={4} style={{ color: "white", margin: 0 }}>
          AIChatBot · 智能数据分析助理
        </Typography.Title>
      </Header>
      <Content style={{ padding: "24px", maxWidth: 960, width: "100%", margin: "0 auto" }}>
        <Routes>
          <Route path="/" element={<Navigate to="/health" replace />} />
          <Route path="/health" element={<HealthCheck />} />
          <Route path="*" element={<Navigate to="/health" replace />} />
        </Routes>
      </Content>
      <Footer style={{ textAlign: "center", color: "#888" }}>
        Phase 1 · Skeleton — 后续 Phase 2 将切换到三栏 Workspace
      </Footer>
    </Layout>
  );
}

export default App;
