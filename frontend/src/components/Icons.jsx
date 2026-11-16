const PATHS = {
  today: ['M8 3v3M16 3v3M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'],
  grid: ['M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v4H4zM14 15h6v4h-6z'],
  upload: ['M12 16V4', 'M8 8l4-4 4 4', 'M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2'],
  chat: ['M20 12a7 7 0 0 1-7 7H8l-4 2.5V12a7 7 0 0 1 7-7h2a7 7 0 0 1 7 7z'],
  check: ['M5 13l4 4L19 7'],
  x: ['M6 6l12 12', 'M18 6L6 18'],
  refresh: ['M20.5 12a8.5 8.5 0 1 1-2.6-6.1', 'M20.5 4.5V10h-5.5'],
  clock: ['M12 8v4.5l3 1.8', 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z'],
  arrowRight: ['M5 12h14', 'M13 6l6 6-6 6'],
  target: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9z', 'M12 13.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z'],
  book: ['M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5V5.5z', 'M8 7h7'],
  flame: ['M12 3s5 4.2 5 8.6a5 5 0 0 1-10 0C7 9.5 8.2 7.6 9.5 6.3 10 8 11 9 12 9c0-2 0-4 0-6z'],
  alert: ['M12 4.5 21 19.5H3L12 4.5z', 'M12 10v4', 'M12 17h.01'],
  send: ['M4 12 20 4l-6.2 16-2.3-6.4L4 12z'],
  plus: ['M12 5v14', 'M5 12h14'],
  menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  sparkles: ['M12 3l1.7 4.8L18.5 9.5 13.7 11.2 12 16l-1.7-4.8L5.5 9.5l4.8-1.7L12 3z', 'M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2z'],
  chart: ['M4 20V6', 'M4 20h16', 'M8 16v-4', 'M12 16V8', 'M16 16v-7'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4.5 20a7.5 7.5 0 0 1 15 0'],
  bolt: ['M13 3 5 14h6l-1 7 8-11h-6l1-7z'],
  file: ['M7 3h7l4 4v14H7z', 'M14 3v4h4'],
  calendar: ['M8 3v3', 'M16 3v3', 'M4 8h16', 'M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'],
}

export default function Icon({ name, className = 'h-4 w-4', strokeWidth = 1.7 }) {
  const paths = PATHS[name] || PATHS.sparkles
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {paths.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  )
}
