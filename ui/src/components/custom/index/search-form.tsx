import { Search } from "lucide-react"

import { Label } from "@/components/ui/label"
import {
    SidebarGroup,
    SidebarGroupContent,
    SidebarInput,
} from "@/components/ui/sidebar"

export function SearchForm({ ...props}: React.ComponentProps<"form">) {
    return (
        <form {...props}>
            <SidebarGroup className="py-0">
                <SidebarGroupContent className="relative">
                    <Label htmlFor="search" className="sr-only">
                        Search
                    </Label>
                    <SidebarInput 
                        id="search"
                        placeholder="Search messages..."
                        className="p1-8"
                    />
                </SidebarGroupContent>
            </SidebarGroup>
        </form>
    )
}