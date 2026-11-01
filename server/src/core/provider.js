// FireRed-380: OpenAI-compatible chat provider facade for upstream Responses consumers.
// No SDK retries: a failed/uncertain model request is surfaced to the operator.
const OpenAI = require('openai');

function toMessages(input = []) {
  const messages = [];
  for (const item of input) {
    if (item.type === 'reasoning') continue;
    if (item.type === 'function_call') {
      messages.push({role: 'assistant', content: null, tool_calls: [{id: item.call_id || item.id,
        type: 'function', function: {name: item.name, arguments: item.arguments}}]});
    } else if (item.type === 'function_call_output') {
      const output = typeof item.output === 'string' ? item.output : JSON.stringify(item.output);
      messages.push({role: 'tool', tool_call_id: item.call_id, content: output});
    } else if (item.role) {
      const raw = item.content;
      const content = typeof raw === 'string' ? raw : (raw || []).map(part => {
        if (['input_text','output_text','text'].includes(part.type)) return {type:'text',text:part.text || ''};
        if (part.type === 'input_image') return {type:'image_url',image_url:{url:part.image_url}};
        return null;
      }).filter(Boolean);
      messages.push({role: item.role === 'developer' ? 'system' : item.role, content});
    }
  }
  return messages;
}

function convertResponse(response) {
  const choice = response?.choices?.[0];
  if (!choice?.message || !['stop', 'tool_calls', 'function_call'].includes(choice.finish_reason))
    throw new Error('Missing, truncated or failed model completion');
  const msg = choice.message;
  const output = [];
  if (msg.content) output.push({type:'message',role:'assistant', content:[{type:'output_text',text:msg.content}]});
  for (const tool of msg.tool_calls || []) {
    if (!tool.id || tool.type !== 'function' || tool.function?.name !== 'execute_action')
      throw new Error('Unsupported or malformed tool call');
    const args = JSON.parse(tool.function.arguments);
    if (!Array.isArray(args.actions) || args.actions.length < 1 || args.actions.length > 10)
      throw new Error('Tool actions must be an array of 1..10 actions');
    output.push({type:'function_call',name:tool.function.name,arguments:tool.function.arguments,call_id:tool.id,id:tool.id});
  }
  if ((msg.tool_calls || []).length > 1) throw new Error('Parallel tool calls are disabled');
  if (!output.length) throw new Error('Empty model response');
  const usage = response.usage || {};
  return {output, usage:{input_tokens:usage.prompt_tokens || 0, output_tokens:usage.completion_tokens || 0,
    total_tokens:usage.total_tokens || 0,input_tokens_details:{cached_tokens:usage.prompt_tokens_details?.cached_tokens || 0}}};
}

function createProvider(settings, injectedClient) {
  if (!['ollama', 'openai'].includes(settings.provider)) throw new Error('Unknown AI provider');
  const url = new URL(settings.baseURL);
  if (settings.provider === 'ollama' && !['127.0.0.1','localhost','[::1]'].includes(url.hostname))
    throw new Error('Ollama must use a local endpoint');
  if (settings.provider === 'openai' && !settings.apiKey) throw new Error('OpenAI requires an explicitly configured key');
  if (url.username || url.password) throw new Error('Credentials must not be embedded in endpoints');
  const localClient = {chat:{completions:{create:async(body,options) => {
    const response = await fetch(settings.baseURL.replace(/\/$/,'') + '/chat/completions', {
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:options.signal,
    });
    if (!response.ok) throw new Error(`Local model HTTP ${response.status}`);
    return response.json();
  }}}};
  const client = injectedClient || (settings.provider === 'ollama' ? localClient : new OpenAI({
    baseURL:settings.baseURL,apiKey:settings.apiKey,timeout:settings.timeout,maxRetries:0,
  }));
  async function complete(request) {
    const tools = (request.tools || []).map(tool => {
      if (tool.type !== 'function') throw new Error('Remote code/container tools are excluded');
      return {type:'function',function:{name:tool.name,description:tool.description,parameters:tool.parameters}};
    });
    const messages = toMessages(request.input);
    if (!settings.vision) for (const message of messages)
      if (Array.isArray(message.content)) message.content = message.content.filter(p => p.type !== 'image_url');
    const body = {model:request.model || settings.model,messages,
      stream:false, max_tokens:Math.min(request.max_output_tokens || 4096, 8192)};
    if (tools.length) Object.assign(body,{tools,tool_choice:request.tool_choice === 'required' ? 'required' : 'auto',parallel_tool_calls:false});
    const response = await client.chat.completions.create(body, {signal:AbortSignal.timeout(settings.timeout)});
    const result = convertResponse(response);
    if (tools.length && request.tool_choice === 'required' && !result.output.some(item => item.type === 'function_call'))
      throw new Error('Model did not provide a required tool call; operator review required');
    return result;
  }
  async function create(request) {
    const result = await complete(request);
    if (!request.stream) return result;
    return (async function*() {
      for (const item of result.output) {
        yield {type:'response.output_item.added',item};
        if (item.type === 'message') yield {type:'response.output_text.delta',delta:item.content[0].text};
        yield {type:'response.output_item.done',item};
      }
      yield {type:'response.completed',response:result};
    })();
  }
  return {responses:{create}, complete};
}
module.exports = {createProvider, toMessages, convertResponse};
