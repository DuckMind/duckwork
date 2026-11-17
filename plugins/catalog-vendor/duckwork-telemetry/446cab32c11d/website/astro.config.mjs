// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightLinksValidator from 'starlight-links-validator';

// https://astro.build/config
export default defineConfig({
	site: 'https://nujovich.github.io',
	base: '/duckwork-telemetry',
	integrations: [
		starlight({
			title: 'duckwork-telemetry',
			logo: { src: './src/assets/logo.svg', alt: '' },
			customCss: ['./src/styles/theme.css'],
			components: { Footer: './src/components/Footer.astro' },
			plugins: [starlightLinksValidator()],
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/DuckMind/duckwork' },
			],
			editLink: {
				baseUrl: 'https://github.com/DuckMind/duckwork',
			},
			// Internals and the Changelog page are generated from ONBOARDING.md / CHANGELOG.md by
			// scripts/sync-docs.mjs. Every other page is hand-written.
			sidebar: [
				{
					label: 'Getting started',
					items: [
						{ label: 'Introduction', slug: 'getting-started/introduction' },
						{ label: 'Installation', slug: 'getting-started/installation' },
						{ label: 'Quick start', slug: 'getting-started/quick-start' },
						{ label: 'Setup wizard', slug: 'getting-started/setup-wizard' },
					],
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Slash commands', slug: 'guides/slash-commands' },
						{ label: 'Standalone CLI', slug: 'guides/standalone-cli' },
						{ label: 'Dashboard', slug: 'guides/dashboard' },
						{ label: 'Budgets', slug: 'guides/budgets' },
						{ label: 'Pricing', slug: 'guides/pricing' },
						{ label: 'Profiles and shared home', slug: 'guides/profiles' },
						{ label: 'Provider probe', slug: 'guides/provider-probe' },
					],
				},
				{
					label: 'Internals',
					collapsed: true,
					items: [{ autogenerate: { directory: 'internals' } }],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Configuration', slug: 'reference/configuration' },
						{ label: 'Known limitations', slug: 'reference/known-limitations' },
						{ label: 'Troubleshooting', slug: 'reference/troubleshooting' },
						{ label: 'Proof of concept', slug: 'reference/proof-of-concept' },
						{ label: 'Changelog', slug: 'reference/changelog' },
					],
				},
			],
		}),
	],
});
