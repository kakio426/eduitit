import type { CommandDispatcher } from '@/command/dispatcher';
import type { CellInfo, DocumentPosition } from '@/core/types';
import type { WasmBridge } from '@/core/wasm-bridge';
import type { InputHandler } from '@/engine/input-handler';
import {
  DeleteSelectionCommand,
  DeleteTextCommand,
  InsertTabCommand,
  InsertTextCommand,
  MergeNextParagraphCommand,
  MergeNextParagraphInCellCommand,
  MergeParagraphCommand,
  MergeParagraphInCellCommand,
  SplitParagraphCommand,
  SplitParagraphInCellCommand,
} from '@/engine/command';

type HostEventSender = (event: string, payload?: Record<string, unknown>) => void;

export interface DoccollabBridgeCommand {
  id?: string;
  type: string;
  action?: 'insert' | 'delete';
  text?: string;
  count?: number;
  direction?: 'forward' | 'backward';
  deletedText?: string;
  start?: DocumentPosition | null;
  end?: DocumentPosition | null;
  position?: DocumentPosition | null;
  row?: number;
  col?: number;
  below?: boolean;
  right?: boolean;
}

interface InstallOptions {
  dispatcher: CommandDispatcher;
  inputHandler: InputHandler;
  postHostEvent: HostEventSender;
  readOnlyMode: boolean;
  wasm: WasmBridge;
}

interface CollaborationState {
  participantCount: number;
}

export interface DoccollabBridgeController {
  applyCommandBatch(batchId: string, commands: DoccollabBridgeCommand[]): { applied: boolean; count: number };
  resetDocumentSession(): void;
  setCollaborationState(state: CollaborationState): void;
}

const TABLE_COMMAND_IDS = new Set([
  'table:insert-row-above',
  'table:insert-row-below',
  'table:delete-row',
  'table:insert-col-left',
  'table:insert-col-right',
  'table:delete-col',
]);

export function installDoccollabBridge(options: InstallOptions): DoccollabBridgeController {
  const {
    dispatcher,
    inputHandler,
    postHostEvent,
    readOnlyMode,
    wasm,
  } = options;
  const inputHandlerAny = inputHandler as unknown as Record<string, unknown>;
  const bridgeState = {
    appliedBatchIds: new Set<string>(),
    applyingRemoteBatch: false,
    commandSequence: 0,
    participantCount: 1,
    selectionTimer: 0,
  };
  const originalExecuteOperation = inputHandler.executeOperation.bind(inputHandler);
  const originalCanUndo = inputHandler.canUndo.bind(inputHandler);
  const originalCanRedo = inputHandler.canRedo.bind(inputHandler);
  const originalPerformUndo = inputHandler.performUndo.bind(inputHandler);
  const originalPerformRedo = inputHandler.performRedo.bind(inputHandler);
  const originalDispatch = dispatcher.dispatch.bind(dispatcher);
  const originalUpdateCaret = typeof inputHandlerAny.updateCaret === 'function'
    ? (inputHandlerAny.updateCaret as (...args: unknown[]) => unknown).bind(inputHandler)
    : null;

  inputHandler.executeOperation = ((descriptor: unknown) => {
    originalExecuteOperation(descriptor as never);
    if (bridgeState.applyingRemoteBatch || readOnlyMode) {
      return;
    }
    const commands = normalizeDescriptor(
      descriptor as Record<string, unknown>,
      wasm,
      bridgeState,
    );
    if (!commands.length) {
      return;
    }
    postHostEvent('commandExecuted', {
      commands,
      selection: buildSelectionPayload(inputHandler, bridgeState.participantCount),
      changedAt: new Date().toISOString(),
    });
  }) as typeof inputHandler.executeOperation;

  inputHandler.canUndo = (() => {
    if (bridgeState.participantCount > 1) {
      return false;
    }
    return originalCanUndo();
  }) as typeof inputHandler.canUndo;

  inputHandler.canRedo = (() => {
    if (bridgeState.participantCount > 1) {
      return false;
    }
    return originalCanRedo();
  }) as typeof inputHandler.canRedo;

  inputHandler.performUndo = (() => {
    if (bridgeState.participantCount > 1) {
      return;
    }
    originalPerformUndo();
  }) as typeof inputHandler.performUndo;

  inputHandler.performRedo = (() => {
    if (bridgeState.participantCount > 1) {
      return;
    }
    originalPerformRedo();
  }) as typeof inputHandler.performRedo;

  dispatcher.dispatch = ((commandId: string, params?: Record<string, unknown>) => {
    const before = captureTableContext(commandId, inputHandler, wasm);
    const result = originalDispatch(commandId, params);
    if (!result || bridgeState.applyingRemoteBatch || readOnlyMode) {
      return result;
    }
    const command = normalizeTableDispatch(commandId, before, bridgeState);
    if (command) {
      postHostEvent('commandExecuted', {
        commands: [command],
        selection: buildSelectionPayload(inputHandler, bridgeState.participantCount),
        changedAt: new Date().toISOString(),
      });
    }
    return result;
  }) as typeof dispatcher.dispatch;

  if (originalUpdateCaret) {
    inputHandlerAny.updateCaret = (...args: unknown[]) => {
      const result = originalUpdateCaret(...args);
      if (!bridgeState.applyingRemoteBatch) {
        scheduleSelectionEvent(inputHandler, bridgeState, postHostEvent);
      }
      return result;
    };
  }

  return {
    applyCommandBatch(batchId, commands) {
      if (!batchId || bridgeState.appliedBatchIds.has(batchId)) {
        return { applied: false, count: 0 };
      }
      bridgeState.appliedBatchIds.add(batchId);
      bridgeState.applyingRemoteBatch = true;
      try {
        let appliedCount = 0;
        commands.forEach((command) => {
          if (applyCommand(command, inputHandler, wasm)) {
            appliedCount += 1;
          }
        });
        return { applied: appliedCount > 0, count: appliedCount };
      } finally {
        bridgeState.applyingRemoteBatch = false;
        scheduleSelectionEvent(inputHandler, bridgeState, postHostEvent);
      }
    },
    resetDocumentSession() {
      bridgeState.appliedBatchIds.clear();
    },
    setCollaborationState(state) {
      bridgeState.participantCount = Math.max(1, Number(state.participantCount || 1));
      scheduleSelectionEvent(inputHandler, bridgeState, postHostEvent);
    },
  };
}

function scheduleSelectionEvent(
  inputHandler: InputHandler,
  bridgeState: { participantCount: number; selectionTimer: number },
  postHostEvent: HostEventSender,
): void {
  if (bridgeState.selectionTimer) {
    window.clearTimeout(bridgeState.selectionTimer);
  }
  bridgeState.selectionTimer = window.setTimeout(() => {
    postHostEvent('selectionChanged', buildSelectionPayload(inputHandler, bridgeState.participantCount));
  }, 60);
}

function buildSelectionPayload(inputHandler: InputHandler, participantCount: number): Record<string, unknown> {
  return {
    cursor: clonePosition(inputHandler.getCursorPosition?.() || null),
    hasSelection: Boolean(inputHandler.hasSelection?.()),
    inCell: Boolean(inputHandler.isInTable?.()),
    participantCount,
  };
}

function normalizeDescriptor(
  descriptor: Record<string, unknown>,
  wasm: WasmBridge,
  bridgeState: { commandSequence: number },
): DoccollabBridgeCommand[] {
  const command = descriptor.command as Record<string, unknown> | undefined;
  if (!command || typeof command.type !== 'string') {
    return [];
  }
  const position = clonePosition((command.position as DocumentPosition | undefined) || null);
  switch (command.type) {
    case 'insertText': {
      if (!position) {
        return [];
      }
      const text = String(command.text || '');
      if (!text) {
        return [];
      }
      if (isCellPosition(position)) {
        const cellInfo = resolveCellInfo(wasm, position);
        return [{
          id: nextCommandId('cell-insert', bridgeState),
          type: 'table_cell_text',
          action: 'insert',
          position,
          row: cellInfo?.row,
          col: cellInfo?.col,
          text,
        }];
      }
      return [{
        id: nextCommandId('insert', bridgeState),
        type: 'insert_text',
        position,
        text,
      }];
    }
    case 'deleteText': {
      if (!position) {
        return [];
      }
      const count = Number(command.count || 1);
      const direction = String(command.direction || 'forward') === 'backward' ? 'backward' : 'forward';
      if (isCellPosition(position)) {
        const cellInfo = resolveCellInfo(wasm, position);
        return [{
          id: nextCommandId('cell-delete', bridgeState),
          type: 'table_cell_text',
          action: 'delete',
          position,
          row: cellInfo?.row,
          col: cellInfo?.col,
          count,
          direction,
          deletedText: command.deletedText ? String(command.deletedText) : undefined,
        }];
      }
      return [{
        id: nextCommandId('delete', bridgeState),
        type: 'delete_text',
        position,
        count,
        direction,
        deletedText: command.deletedText ? String(command.deletedText) : undefined,
      }];
    }
    case 'insertTab':
      return position ? [{
        id: nextCommandId('tab', bridgeState),
        type: 'insert_tab',
        position,
      }] : [];
    case 'splitParagraph':
    case 'splitParagraphInCell':
      return position ? [{
        id: nextCommandId('split', bridgeState),
        type: 'split_paragraph',
        position,
      }] : [];
    case 'mergeParagraph':
    case 'mergeNextParagraph':
    case 'mergeParagraphInCell':
    case 'mergeNextParagraphInCell':
      return position ? [{
        id: nextCommandId('merge', bridgeState),
        type: 'merge_paragraph',
        action: command.type.includes('Next') ? 'delete' : 'insert',
        position,
      }] : [];
    case 'deleteSelection':
      return [{
        id: nextCommandId('selection', bridgeState),
        type: 'delete_selection',
        start: clonePosition((command.start as DocumentPosition | undefined) || null),
        end: clonePosition((command.end as DocumentPosition | undefined) || null),
      }];
    default:
      return [];
  }
}

function captureTableContext(
  commandId: string,
  inputHandler: InputHandler,
  wasm: WasmBridge,
): Record<string, unknown> | null {
  if (!TABLE_COMMAND_IDS.has(commandId)) {
    return null;
  }
  const position = clonePosition(inputHandler.getCursorPosition?.() || null);
  if (!position || position.parentParaIndex == null) {
    return null;
  }
  const cellInfo = resolveCellInfo(wasm, position);
  return {
    position,
    row: cellInfo?.row,
    col: cellInfo?.col,
  };
}

function normalizeTableDispatch(
  commandId: string,
  before: Record<string, unknown> | null,
  bridgeState: { commandSequence: number },
): DoccollabBridgeCommand | null {
  if (!before || !before.position) {
    return null;
  }
  const base = {
    id: nextCommandId('table', bridgeState),
    position: before.position as DocumentPosition,
  };
  switch (commandId) {
    case 'table:insert-row-above':
      return { ...base, type: 'table_row_insert', row: Number(before.row || 0), below: false };
    case 'table:insert-row-below':
      return { ...base, type: 'table_row_insert', row: Number(before.row || 0), below: true };
    case 'table:delete-row':
      return { ...base, type: 'table_row_delete', row: Number(before.row || 0) };
    case 'table:insert-col-left':
      return { ...base, type: 'table_col_insert', col: Number(before.col || 0), right: false };
    case 'table:insert-col-right':
      return { ...base, type: 'table_col_insert', col: Number(before.col || 0), right: true };
    case 'table:delete-col':
      return { ...base, type: 'table_col_delete', col: Number(before.col || 0) };
    default:
      return null;
  }
}

function applyCommand(command: DoccollabBridgeCommand, inputHandler: InputHandler, wasm: WasmBridge): boolean {
  try {
    switch (command.type) {
      case 'insert_text':
        if (!command.position) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: new InsertTextCommand(command.position, String(command.text || '')),
        });
        return true;
      case 'delete_text':
        if (!command.position) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: new DeleteTextCommand(
            command.position,
            Number(command.count || 1),
            command.direction === 'backward' ? 'backward' : 'forward',
            command.deletedText ? String(command.deletedText) : undefined,
          ),
        });
        return true;
      case 'insert_tab':
        if (!command.position) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: new InsertTabCommand(command.position),
        });
        return true;
      case 'split_paragraph':
        if (!command.position) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: isCellPosition(command.position)
            ? new SplitParagraphInCellCommand(command.position)
            : new SplitParagraphCommand(command.position),
        });
        return true;
      case 'merge_paragraph':
        if (!command.position) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: buildMergeCommand(command.position, command.action === 'delete'),
        });
        return true;
      case 'delete_selection':
        if (!command.start || !command.end) {
          return false;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: new DeleteSelectionCommand(command.start, command.end),
        });
        return true;
      case 'table_cell_text':
        if (!command.position) {
          return false;
        }
        if (command.action === 'delete') {
          inputHandler.executeOperation({
            kind: 'command',
            command: new DeleteTextCommand(
              command.position,
              Number(command.count || 1),
              command.direction === 'backward' ? 'backward' : 'forward',
              command.deletedText ? String(command.deletedText) : undefined,
            ),
          });
          return true;
        }
        inputHandler.executeOperation({
          kind: 'command',
          command: new InsertTextCommand(command.position, String(command.text || '')),
        });
        return true;
      case 'table_row_insert':
      case 'table_row_delete':
      case 'table_col_insert':
      case 'table_col_delete':
        return applyTableMutation(command, inputHandler, wasm);
      default:
        return false;
    }
  } catch (error) {
    console.error('[doccollab-bridge] applyCommand failed', command, error);
    return false;
  }
}

function applyTableMutation(command: DoccollabBridgeCommand, inputHandler: InputHandler, wasm: WasmBridge): boolean {
  if (!command.position || command.position.parentParaIndex == null || command.position.controlIndex == null) {
    return false;
  }
  inputHandler.moveCursorTo(command.position);
  const {
    sectionIndex,
    parentParaIndex,
    controlIndex,
  } = command.position;
  switch (command.type) {
    case 'table_row_insert':
      wasm.insertTableRow(sectionIndex, parentParaIndex, controlIndex, Number(command.row || 0), Boolean(command.below));
      break;
    case 'table_row_delete':
      wasm.deleteTableRow(sectionIndex, parentParaIndex, controlIndex, Number(command.row || 0));
      break;
    case 'table_col_insert':
      wasm.insertTableColumn(sectionIndex, parentParaIndex, controlIndex, Number(command.col || 0), Boolean(command.right));
      break;
    case 'table_col_delete':
      wasm.deleteTableColumn(sectionIndex, parentParaIndex, controlIndex, Number(command.col || 0));
      break;
    default:
      return false;
  }
  inputHandler.triggerAfterEdit();
  return true;
}

function buildMergeCommand(position: DocumentPosition, forwardDelete: boolean) {
  if (isCellPosition(position)) {
    return forwardDelete
      ? new MergeNextParagraphInCellCommand(position)
      : new MergeParagraphInCellCommand(position);
  }
  return forwardDelete
    ? new MergeNextParagraphCommand(position)
    : new MergeParagraphCommand(position);
}

function resolveCellInfo(wasm: WasmBridge, position: DocumentPosition): CellInfo | null {
  if (position.parentParaIndex == null) {
    return null;
  }
  if ((position.cellPath?.length ?? 0) > 1) {
    return wasm.getCellInfoByPath(position.sectionIndex, position.parentParaIndex, JSON.stringify(position.cellPath || []));
  }
  if (position.controlIndex == null || position.cellIndex == null) {
    return null;
  }
  return wasm.getCellInfo(position.sectionIndex, position.parentParaIndex, position.controlIndex, position.cellIndex);
}

function isCellPosition(position: DocumentPosition): boolean {
  return position.parentParaIndex != null;
}

function clonePosition(position: DocumentPosition | null): DocumentPosition | null {
  if (!position) {
    return null;
  }
  return JSON.parse(JSON.stringify(position)) as DocumentPosition;
}

function nextCommandId(prefix: string, bridgeState: { commandSequence: number }): string {
  bridgeState.commandSequence += 1;
  return `${prefix}-${Date.now()}-${bridgeState.commandSequence}`;
}
