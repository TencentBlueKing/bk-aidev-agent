import { describe, expect, it } from 'vitest';

import { ActivityType, MessageRole, MessageType } from '../../message/type';
import { transferMessage2MessageApi, transferMessageApi2Message } from './message';

import type {
  IActivityMessage,
  IBinaryInputContent,
  IBinaryInputContentApi,
  IKnowledgeRag,
  IKnowledgeRagApi,
  IMessage,
  IMessageApi,
  IReferenceDocument,
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

describe('reference document transform', () => {
  const externalUrl = 'https://iwiki.example.com/p/1';
  const previewUrl = 'https://aidev.example.com/knowledgebase?knowledgeName=a.md';
  const referenceApi = [{ name: 'doc', origin_file_url: externalUrl, url: previewUrl }];
  const activityApi = {
    ...baseApi,
    role: MessageRole.Activity,
    activity_type: ActivityType.ReferenceDocument,
    content: referenceApi,
  } as unknown as IMessageApi;

  it('exposes the external link as both originFile and originFileUrl', () => {
    const result = transferMessageApi2Message(activityApi) as IActivityMessage;

    expect(result.content).toEqual([
      { name: 'doc', originFile: externalUrl, originFileUrl: externalUrl, url: previewUrl },
    ]);
  });

  it('fills both fields inside knowledge rag content', () => {
    const ragApi: IKnowledgeRagApi = { content: 'answer', reference_document: referenceApi };
    const result = transferMessageApi2Message({
      ...activityApi,
      activity_type: ActivityType.KnowledgeRag,
      content: ragApi,
    } as unknown as IMessageApi) as IActivityMessage;

    expect((result.content as IKnowledgeRag).referenceDocument[0]).toMatchObject({
      originFile: externalUrl,
      originFileUrl: externalUrl,
    });
  });

  it('keeps documents without an external link empty', () => {
    const result = transferMessageApi2Message({
      ...activityApi,
      content: [{ name: 'upload.md', url: previewUrl }],
    } as unknown as IMessageApi) as IActivityMessage;

    expect((result.content as IReferenceDocument)[0]).toMatchObject({
      originFile: undefined,
      originFileUrl: undefined,
    });
  });

  it('accepts originFile when converting back to API', () => {
    const result = transferMessage2MessageApi({
      ...baseApi,
      messageId: 'msg-1',
      role: MessageRole.Activity,
      activityType: ActivityType.ReferenceDocument,
      content: [{ name: 'doc', originFile: externalUrl, url: previewUrl }],
    } as unknown as IMessage);

    expect(result.content).toEqual([{ name: 'doc', origin_file_url: externalUrl, url: previewUrl }]);
  });

  it('survives an API → local → API round trip', () => {
    const backToApi = transferMessage2MessageApi(transferMessageApi2Message(activityApi));

    expect(backToApi.content).toEqual(referenceApi);
  });
});
