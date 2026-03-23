import adapterAuto from '@sveltejs/adapter-auto';
import adapterNode from '@sveltejs/adapter-node';

// In Docker environments, use adapter-node (more reliable for Node.js servers)
// Otherwise, use adapter-auto for development and other platforms
const adapter = process.env.DOCKER_BUILD ? adapterNode() : adapterAuto();

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter
	}
};

export default config;
