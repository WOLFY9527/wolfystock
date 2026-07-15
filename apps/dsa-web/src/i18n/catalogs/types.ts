type CatalogShape<T> = T extends string
  ? string
  : T extends readonly (infer Item)[]
    ? readonly CatalogShape<Item>[]
    : { readonly [Key in keyof T]: CatalogShape<T[Key]> };

export type LocaleCatalog = CatalogShape<typeof import('./zh').zhCatalog>;
