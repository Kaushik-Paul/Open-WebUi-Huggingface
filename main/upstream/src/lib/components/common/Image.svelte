<script lang="ts">
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { safeImageUrl } from '$lib/utils/safeImageUrl';

	import { settings } from '$lib/stores';
	import { onDestroy, onMount } from 'svelte';
	import ImagePreview from './ImagePreview.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import Photo from '$lib/components/icons/Photo.svelte';
	import { getContext } from 'svelte';

	export let src = '';
	export let alt = '';
	export let allowExternal = false;

	export let className = ` w-full ${($settings?.highContrastMode ?? false) ? '' : 'outline-hidden focus:outline-hidden'}`;

	export let imageClassName = 'rounded-lg';

	export let dismissible = false;
	export let onDismiss = () => {};

	/** Called when the image fails to load, e.g. its file has since been deleted. */
	export let onError: () => void = () => {};

	const i18n = getContext('i18n');

	let _src = '';
	$: _src = safeImageUrl(src.startsWith('/') ? `${WEBUI_BASE_URL}${src}` : src, allowExternal);

	let displaySrc = '';
	let loadedSrc = '';
	let objectUrl = '';
	let mounted = false;
	let loadVersion = 0;

	const loadImage = async (url: string) => {
		loadedSrc = url;
		const version = ++loadVersion;
		if (objectUrl) {
			URL.revokeObjectURL(objectUrl);
			objectUrl = '';
		}
		displaySrc = '';
		failed = false;
		const parsed = new URL(url, window.location.origin);
		const privateFile = parsed.origin === window.location.origin &&
			/^\/api\/v1\/files\/[^/]+\/content$/.test(parsed.pathname);
		if (!privateFile) {
			displaySrc = url;
			return;
		}
		try {
			const response = await fetch(url, {
				headers: { Authorization: `Bearer ${localStorage.token}` }
			});
			if (!response.ok) throw new Error(`Image unavailable: ${response.status}`);
			const blob = await response.blob();
			if (version !== loadVersion) return;
			objectUrl = URL.createObjectURL(blob);
			displaySrc = objectUrl;
		} catch {
			if (version === loadVersion) handleError();
		}
	};

	onMount(() => {
		mounted = true;
		loadImage(_src);
	});
	$: if (mounted && _src !== loadedSrc) loadImage(_src);
	onDestroy(() => {
		loadVersion++;
		if (objectUrl) URL.revokeObjectURL(objectUrl);
	});

	let showImagePreview = false;

	let failed = false;
	let attemptedSrc = '';
	$: compactUnavailable = /(?:^|\s)(?:size-|w-|h-)/.test(imageClassName);
	$: if (_src !== attemptedSrc) {
		attemptedSrc = _src;
		failed = false;
	}

	const handleError = () => {
		failed = true;
		showImagePreview = false;
		onError();
	};
</script>

{#if !failed}
	<ImagePreview bind:show={showImagePreview} src={displaySrc} {alt} />
{/if}

<div class=" relative group w-fit flex items-center">
	{#if failed}
		<div
			class="{imageClassName} inline-flex {compactUnavailable
				? ''
				: 'h-[1.6875rem] min-w-8 gap-1.5 px-2'} items-center justify-center overflow-hidden border border-gray-100/50 bg-gray-50/40 text-gray-500 dark:border-white/[0.04] dark:bg-white/[0.03] dark:text-gray-400"
			data-cy="image-unavailable"
		>
			<Photo className="size-3.5 shrink-0" strokeWidth="1.5" />
			<span class:hidden={compactUnavailable} class="truncate text-xs">
				{$i18n.t('Image unavailable')}
			</span>
		</div>
	{:else if displaySrc}
		<button
			class={className}
			on:click={() => {
				showImagePreview = true;
			}}
			aria-label={$i18n.t('Show image preview')}
			type="button"
		>
			<img
				src={displaySrc}
				{alt}
				class={imageClassName}
				draggable="false"
				data-cy="image"
				on:error={handleError}
			/>
		</button>
	{/if}

	{#if dismissible}
		<div class=" absolute -top-1 -right-1">
			<button
				aria-label={$i18n.t('Remove image')}
				class=" bg-white text-black border border-white rounded-full hover-reveal transition"
				type="button"
				on:click={() => {
					onDismiss();
				}}
			>
				<XMark className={'size-4'} />
			</button>
		</div>
	{/if}
</div>
