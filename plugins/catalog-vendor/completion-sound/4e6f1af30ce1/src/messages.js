// UI strings. English is the fallback for every other app language.
export default {
  en: {
    preview: 'Preview',
    sound: {
      title: 'Completion sound',
      description: 'Plays when a turn finishes.',
      none: 'No sound',
      myFiles: 'My files',
      presets: 'Duckwork presets'
    },
    night: {
      title: 'Different sound at night',
      description: 'Use another sound during the hours below.',
      hours: 'Night hours',
      sound: 'Night sound'
    },
    files: {
      title: 'My audio files',
      description: (max, kb) => `Add up to ${max} files (mp3, wav, ogg, …), ${kb} KB each.`,
      add: 'Add file…',
      remove: 'Remove',
      tooMany: max => `You can keep up to ${max} files. Remove one first.`,
      tooBig: kb => `The file is larger than ${kb} KB.`,
      saveFailed: reason => `Could not save the file: ${reason}`
    },
    volume: {
      title: 'File volume',
      description: 'Applies to your files. Presets play at Duckwork’ own level.'
    },
    note: {
      builtin:
        'Duckwork’ own completion sound still plays alongside this one: Duckwork has no setting to turn it off yet, and plugins cannot switch it off.'
    }
  },
  ko: {
    preview: '미리듣기',
    sound: {
      title: '완료 소리',
      description: '응답이 끝나면 난다.',
      none: '소리 없음',
      myFiles: '내 파일',
      presets: 'Duckwork 기본 소리'
    },
    night: {
      title: '밤에는 다른 소리',
      description: '아래 시간대에는 다른 소리를 낸다.',
      hours: '야간 시간대',
      sound: '야간 소리'
    },
    files: {
      title: '내 소리 파일',
      description: (max, kb) => `파일을 ${max}개까지 넣을 수 있다(mp3, wav, ogg 등, 파일당 ${kb} KB).`,
      add: '파일 추가…',
      remove: '삭제',
      tooMany: max => `파일은 ${max}개까지 넣을 수 있다. 하나를 먼저 지워라.`,
      tooBig: kb => `파일이 ${kb} KB보다 크다.`,
      saveFailed: reason => `파일을 저장하지 못했다: ${reason}`
    },
    volume: {
      title: '파일 음량',
      description: '내 파일에만 적용된다. 기본 소리는 Duckwork가 정한 음량으로 난다.'
    },
    note: {
      builtin: 'Duckwork 자체 완료 소리도 함께 난다. Duckwork에는 아직 이 소리를 끄는 설정이 없고, 플러그인이 끌 수도 없다.'
    }
  }
}
