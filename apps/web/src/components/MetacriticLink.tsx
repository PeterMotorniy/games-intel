import { metacriticGameUrl } from "../lib/format";

type MetacriticLinkProps = {
  slug: string;
  listingUrl?: string | null;
};

export function MetacriticLink({ slug, listingUrl }: MetacriticLinkProps) {
  const href = metacriticGameUrl(slug, listingUrl);
  return (
    <a
      className="metacritic-link"
      href={href}
      rel="noreferrer"
      target="_blank"
    >
      <span className="metacritic-link__mark" aria-hidden="true">
        M
      </span>
      <span className="metacritic-link__text">Metacritic</span>
    </a>
  );
}
