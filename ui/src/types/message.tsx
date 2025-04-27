/**
 * All Types necessary for the basic UI
 */

/**Central data storage */
export type MessageDataStore = {
    threadID: number;
    rootMessageID: number;
    messageTree: Record<number, Message>;
    branchSelectionSet: Set<number>;
    messageList: number[];
}

export type Message = {
    id: number;
    role: string;
    content: string;
    timestamp: string;
    parentID: number|null;
    childIDs: number[];
}