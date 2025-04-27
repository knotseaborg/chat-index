const FAIL_MODE = true

import { Message, MessageDataStore } from "@/types/message";
import { AssertionError } from "assert";

export function fetchMessageData(threadID: number): MessageDataStore {
    let messageData: MessageDataStore = {
        threadID: 1,
        rootMessageID: 1,
        messageTree: {
            1: { "id": 1, "role": "user", "content": "Hello!", "timestamp": "10:00 am", "parentID": null, "childIDs": [2, 3] },
            2: { "id": 2, "role": "assistant", "content": "Hello there!", "timestamp": "10:01 am", "parentID": 1, "childIDs": [4] },
            3: { "id": 3, "role": "user", "content": "Hello! Lorem ipsum dolores", "timestamp": "10:02 am", "parentID": 1, "childIDs": [] },
            4: { "id": 4, "role": "assistant", "content": "Dolores, like Dolores Umbridge!?", "timestamp": "10:03 am", "parentID": 2, "childIDs": [] },
        },
        branchSelectionSet: new Set([]), // state of branches
        messageList: []
    }

    return messageData
}

export function updateBranchSelection(data: MessageDataStore): void {
    /**
     * Updates the branchSelectionSet with the contents of the messageList
     * Is Idempotent
     */
    data.branchSelectionSet.clear()
    data.messageList.forEach((id) => {
        let parentID = data.messageTree[id].parentID
        if (parentID != null && data.messageTree[parentID].childIDs.length > 1) {
            data.branchSelectionSet.add(id)
        }
    })
}

export function generateMessageList(data: MessageDataStore): number[] {
    /**
     * Generates list of messages using path saved in branchSelectionSet
     * Is Idempotent
     */

    // Begin iteration from the root node of the tree
    let rootID: number = data.rootMessageID;
    if (!(rootID in data.messageTree)) {
        throw new AssertionError({ message: `rootID ${rootID} does not exist in messageTree with threadID ${data.threadID}` })
    }
    let node: Message | null = data.messageTree[rootID];

    let messageList: number[] = []
    while (node != null) {
        messageList.push(node.id);
        // First, assign default value of nextNode
        let nextNode: Message | null = node.childIDs.length > 0 ? data.messageTree[node.childIDs[0]] : null;
        for (let i = 0; i < node.childIDs.length; i++) {
            let childID = node.childIDs[i]
            // Override nextNode if path allows
            if (data.branchSelectionSet.has(node.childIDs[i])) {
                if (!(childID in data.messageTree)) {
                    throw new AssertionError({ message: `childID ${childID} does not exist in messageTree with threadID ${data.threadID}` })
                }
                nextNode = data.messageTree[childID];
            }
        }
        node = nextNode;
    }
    return messageList
}