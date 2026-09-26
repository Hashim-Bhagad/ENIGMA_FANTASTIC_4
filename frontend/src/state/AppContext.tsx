import React, { createContext, useContext, useMemo, useState } from 'react';
import { demoProducts, demoProfile, type Product } from '@/src/data/demo';

type AppContextValue = {
  product: Product;
  setProduct: (product: Product) => void;
  saved: string[];
  toggleSaved: (id: string) => void;
  search: string;
  setSearch: (value: string) => void;
  allergens: string[];
  toggleAllergen: (value: string) => void;
  conditions: string[];
  toggleCondition: (value: string) => void;
  products: Product[];
  profileName: string;
  setProfileName: (name: string) => void;
  labelPhoto: string | null;
  setLabelPhoto: (uri: string | null) => void;
  sodiumLimit: string;
  setSodiumLimit: (value: string) => void;
};
const Context = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: React.PropsWithChildren) {
  const [product, setProduct] = useState<Product>(demoProducts[0]);
  const [saved, setSaved] = useState<string[]>(['crackers-01', 'cereal-01']);
  const [search, setSearch] = useState('');
  const [allergens, setAllergens] = useState<string[]>(demoProfile.allergens);
  const [conditions, setConditions] = useState<string[]>(demoProfile.conditions);
  const [profileName, setProfileName] = useState(demoProfile.name);
  const [labelPhoto, setLabelPhoto] = useState<string | null>(null);
  const [sodiumLimit, setSodiumLimit] = useState('');
  const value = useMemo(() => ({ product, setProduct, saved,
    toggleSaved: (id: string) => setSaved(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]),
    search, setSearch,
    allergens,
    toggleAllergen: (item: string) => setAllergens(current => current.includes(item) ? current.filter(value => value !== item) : [...current, item]),
    conditions,
    toggleCondition: (item: string) => setConditions(current => current.includes(item) ? current.filter(value => value !== item) : [...current, item]),
    products: demoProducts, profileName, setProfileName, labelPhoto, setLabelPhoto, sodiumLimit, setSodiumLimit,
  }), [product, saved, search, allergens, conditions, profileName, labelPhoto, sodiumLimit]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useApp() {
  const context = useContext(Context);
  if (!context) throw new Error('useApp must be used inside AppProvider');
  return context;
}
