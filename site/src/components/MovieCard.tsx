import { groupByExperience, hasCollectedShowtimes, showtimesFor } from '../lib/format'
import type { Movie } from '../types'

export function MovieCard({ movie, date }: { movie: Movie; date: string }) {
  const meta = [movie.rating, movie.language, movie.runtime_min ? `${movie.runtime_min} min` : null]
    .filter(Boolean)
    .join(' · ')

  return (
    <article className="movie">
      {movie.poster_url && (
        <img
          className="movie__poster"
          src={movie.poster_url}
          alt={movie.title}
          // Hot-linked from the cinema's CDN. no-referrer avoids leaking where
          // the request came from and dodges naive hot-link blocking; a failure
          // leaves the styled background, never a broken-image icon.
          referrerPolicy="no-referrer"
          loading="lazy"
        />
      )}
      <div className="movie__body">
        <h3 className="movie__title">{movie.title}</h3>
        {meta && <p className="movie__meta">{meta}</p>}
        <Showtimes movie={movie} date={date} />
      </div>
    </article>
  )
}

function Showtimes({ movie, date }: { movie: Movie; date: string }) {
  // "Not collected" and "no screenings" are genuinely different things here.
  // VOX only scrapes the day its page opens on, so most days are unknown -
  // rendering an empty list would claim the cinema is shut.
  if (!hasCollectedShowtimes(movie, date)) {
    return <p className="movie__note">Showtimes not collected for this day.</p>
  }

  const groups = groupByExperience(showtimesFor(movie, date))
  if (groups.length === 0) {
    return <p className="movie__note">No screenings on this day.</p>
  }

  return (
    <div className="showtimes">
      {groups.map((group) => (
        <div key={group.experience} className="showtimes__group">
          <p className="showtimes__experience">{group.experience}</p>
          <ul className="showtimes__list">
            {group.showtimes.map((showtime, index) => (
              <li key={`${showtime.time}-${index}`}>
                {/* Sold out and already-started times stay visible but dimmed;
                    hiding them makes a busy day look empty. */}
                <span
                  className={
                    showtime.available ? 'showtime' : 'showtime showtime--unavailable'
                  }
                >
                  {showtime.time}
                </span>
                {showtime.attributes.map((attribute) => (
                  <span key={attribute} className="tag">
                    {attribute}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
