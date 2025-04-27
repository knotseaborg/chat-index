import { HistorySidebar } from "@/components/custom/history/sidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator"
import { useState } from "react";
import { IndexSidebar } from "@/components/custom/index/sidebar";
import Chat from "@/components/custom/chat_panel";

export default function Home() {
    return (
        <div className="flex">
            <SidebarProvider>
                <HistorySidebar side="left"/>
                <SidebarInset>
                    <header className="flex h-16 shrink-0 items-center gap-2 px-4">
                        <SidebarTrigger className="-m1-1"/>
                        <Separator orientation="vertical" className="mr-2 h-4"/>
                        <h2>Chat Application</h2>
                    </header>
                </SidebarInset>
            </SidebarProvider>
            <div className="flex gap-4 p-4">
                <Chat/>
            </div>
            <SidebarProvider>
                <SidebarInset className="flex flex-row-reverse">
                    <IndexSidebar side="right"/>
                    <header className="flex h-16 shrink-0 items-center gap-2 px-4">
                        <Separator orientation="vertical" className="mr-2 h-4"/>
                        <SidebarTrigger className="-m1-1"/>
                    </header>
                </SidebarInset>
            </SidebarProvider>
        </div>
    );
}
