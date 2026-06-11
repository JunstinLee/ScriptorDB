// src/App.tsx 修改后的完整内容
import { Button, Input } from "@heroui/react";
import { Send, Sparkles } from "lucide-react";

export default function App() {
  return (
    <div className="flex h-screen flex-col items-center justify-center bg-slate-950 p-4 text-white">
      <div className="w-full max-w-md space-y-4">
        <div className="flex items-center gap-2 text-xl font-bold">
          <Sparkles className="text-blue-500" />
          <span>AI Agent 终端</span>
        </div>
        
        <div className="flex gap-2">
          <Input 
            placeholder="向你的 Agent 发送指令..." 
            className="dark"
          />
          
          {/* ⚡️ 这里是修改后的 v3 规范按钮 */}
          <Button variant="primary" isIconOnly>
            <Send className="h-4 w-4" />
          </Button>
          
        </div>
      </div>
    </div>
  );
}