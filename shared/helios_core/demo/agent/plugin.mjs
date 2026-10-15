// Official DeepSeek Harness Cordis plugin. Only these tools reach the Python bridge.
export const name = 'helios-semantic-tools';
export const inject = ['tools'];
export function apply(ctx, config) {
  for (const tool of config.tools) ctx.tools.register({
    ...tool,
    output: {schema: {type:'string'}, render: (_args, value) => [{type:'text',text:value}]},
    async execute(args, exec) {
      const response = await fetch(process.env.HELIOS_HARNESS_BRIDGE, {
        method:'POST', signal:exec.signal,
        headers:{'Content-Type':'application/json','Authorization':`Bearer ${process.env.HELIOS_HARNESS_BRIDGE_TOKEN}`},
        body:JSON.stringify({tool:tool.name,args})
      });
      if (!response.ok) throw new Error('Semantic tool rejected the request.');
      return await response.text();
    }
  });
}
