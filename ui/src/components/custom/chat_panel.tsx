/**
 * Need to have branch management
 * 
 * When multiple children are there, render the branch well.
 */

import { fetchMessageData, generateMessageList } from "@/store/chat"
import { Message as MessageProps } from "@/types/message"

function Message(props: MessageProps) {
    return <div key={props.id.toString()} className={`${props["role"] == "user" ? "pl-2" : "pr-2"}`}>
        <label>{props.role}</label>
        <p>{props.content}</p>
    </div>
}

function MessageList({ messages }: { messages: MessageProps[] }) {
    return <div>
        {messages.map((message, i) => Message(message))}
    </div>
}

export default function Chat() {
    /*Need a chat pane*/
    let threadID = 1;
    let messageData = fetchMessageData(threadID);
    let messageIDs = generateMessageList(messageData)
    return MessageList({ messages: messageIDs.map((id) => messageData.messageTree[id]) })
    /** Need message boxes */
    /*Need an input section*/
}