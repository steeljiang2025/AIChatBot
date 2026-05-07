import { http } from "./http";
export async function fetchHealth() {
    const resp = await http.get("/health");
    return resp.data;
}
