import { describe, expect, it } from 'vitest';

import { MessageRole, MessageStatus, MessageType } from '../../message/type';
import { transferMessage2MessageApi, transferMessageApi2Message } from './message';

import type {
  IBinaryInputContent,
  IBinaryInputContentApi,
  IInfoMessage,
  IInfoMessageApi,
  IMessage,
  IMessageApi,
} from '../../message/type';

const binaryApi: IBinaryInputContentApi = {
  type: MessageType.Binary,
  id: 'files/report.pdf',
  output_id: 'files/report.pdf',
  filename: 'report.pdf',
  mime_type: 'application/pdf',
  size: 1909,
};

const binaryLocal: IBinaryInputContent = {
  type: MessageType.Binary,
  id: 'files/report.pdf',
  outputId: 'files/report.pdf',
  filename: 'report.pdf',
  mimeType: 'application/pdf',
  size: 1909,
};

const baseApi = {
  id: 1,
  message_id: 'msg-1',
  role: MessageRole.User,
  status: 'complete',
} as unknown as IMessageApi;

describe('user message binary content transform', () => {
  it('keeps output_id when converting from API', () => {
    const result = transferMessageApi2Message({ ...baseApi, content: [binaryApi] } as IMessageApi);

    expect((result.content as IBinaryInputContent[])[0]).toMatchObject({
      outputId: 'files/report.pdf',
      filename: 'report.pdf',
      mimeType: 'application/pdf',
    });
  });

  it('keeps outputId when converting to API', () => {
    const result = transferMessage2MessageApi({
      ...baseApi,
      messageId: 'msg-1',
      content: [binaryLocal],
    } as unknown as IMessage);

    expect((result.content as IBinaryInputContentApi[])[0]).toMatchObject({
      output_id: 'files/report.pdf',
      filename: 'report.pdf',
      mime_type: 'application/pdf',
    });
  });

  it('survives an API → local → API round trip', () => {
    const local = transferMessageApi2Message({ ...baseApi, content: [binaryApi] } as IMessageApi);
    const backToApi = transferMessage2MessageApi(local);

    expect((backToApi.content as IBinaryInputContentApi[])[0].output_id).toBe('files/report.pdf');
  });

  it('leaves output_id undefined for legacy attachments without it', () => {
    const { output_id: _omitted, ...legacy } = binaryApi;
    const result = transferMessageApi2Message({ ...baseApi, content: [legacy] } as IMessageApi);

    expect((result.content as IBinaryInputContent[])[0].outputId).toBeUndefined();
  });
});

describe('info message fork_info transform', () => {
  const forkInfo = {
    source_session_code: 'a1b2c3d4',
    source_content_id: 1052,
    last_copied_content_id: 1053,
  };

  const infoApi = {
    id: 2001,
    message_id: 'fork-1',
    role: MessageRole.Info,
    status: MessageStatus.Complete,
    content: '其他会话中继续',
    property: { fork_info: forkInfo },
  } as IInfoMessageApi;

  it('keeps property.fork_info when converting from API', () => {
    const result = transferMessageApi2Message(infoApi) as IInfoMessage;

    expect(result.property?.fork_info).toEqual(forkInfo);
    expect(result.content).toBe('其他会话中继续');
  });

  it('keeps property.fork_info when converting to API', () => {
    const result = transferMessage2MessageApi({
      id: 2001,
      messageId: 'fork-1',
      role: MessageRole.Info,
      status: MessageStatus.Complete,
      content: '其他会话中继续',
      property: { fork_info: forkInfo },
    } as IInfoMessage) as IInfoMessageApi;

    expect(result.property?.fork_info).toEqual(forkInfo);
  });

  it('survives an API → local → API round trip', () => {
    const local = transferMessageApi2Message(infoApi);
    const backToApi = transferMessage2MessageApi(local) as IInfoMessageApi;

    expect(backToApi.property?.fork_info).toEqual(forkInfo);
  });
});
