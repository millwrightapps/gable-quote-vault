"""Test helper: a synthetic timed transcript in the importer's format."""


def transcript(*lines, episode=10):
    return dict(youtubeVideoId='abcdefghijk', show='RP', episode=episode, episodeTitle=f'Fixture [{episode}]',
                segments=[dict(start=start, text=text) for start, text in lines])
