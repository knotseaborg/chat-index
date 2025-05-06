import Chat from "@/components/custom/chat_panel";

export default function Home() {
    return (
        <div className="grid grid-cols-3 grid-gap-4">
            <div className="items-center">Left History Panel</div>
            <div className="items-center w-200">
                <Chat/>
            </div>
            <div className="items-center">
                
            </div>
        </div>
    );
}
