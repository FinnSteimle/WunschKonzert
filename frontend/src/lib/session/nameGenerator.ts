const ADJECTIVES = [
    'Crazy',
    'Happy',
    'Sneaky',
    'Wild',
    'Brave',
    'Chill',
    'Funky',
    'Mighty',
    'Swift',
    'Lazy',
    'Fierce',
    'Cosmic',
    'Zesty',
    'Fuzzy',
    'Lucky',
    'Mystic',
    'Silly',
    'Quiet',
    'Rapid',
    'Sly',
    'Bold',
    'Epic',
    'Tiny',
    'Loud',
    'Shiny',
    'Naughty'
];

const COLORS = [
    'Pink',
    'Blue',
    'Red',
    'Green',
    'Gold',
    'Silver',
    'Violet',
    'Coral',
    'Teal',
    'Amber',
    'Cyan',
    'Crimson',
    'Scarlet',
    'Bronze',
    'Copper'
];

const ANIMALS = [
    'Lizard',
    'Globi',
    'Pingu',
    'Panda',
    'Fox',
    'Wolf',
    'Eagle',
    'Otter',
    'Tiger',
    'Falcon',
    'Koala',
    'Shark',
    'Dolphin',
    'Gecko',
    'Parrot',
    'Bison',
    'Owl',
    'Cobra',
    'Moose',
    'Puma',
    'Badger',
    'Viper',
    'Wombat',
    'Jaguar',
    'Doggo'
];

function pick<T>(arr: readonly T[]): T {
    return arr[Math.floor(Math.random() * arr.length)];
}

export function generateRandomDisplayName(): string {
    return `${pick(ADJECTIVES)}${pick(COLORS)}${pick(ANIMALS)}`;
}

/**
 * Matches names produced by {@link generateRandomDisplayName}.
 * Used to detect auto-generated names that the user never customised.
 */
export const AUTO_GENERATED_NAME_RE = new RegExp(
    `^(${ADJECTIVES.join('|')})(${COLORS.join('|')})(${ANIMALS.join('|')})$`
);